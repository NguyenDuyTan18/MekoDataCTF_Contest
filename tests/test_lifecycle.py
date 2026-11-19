"""Regression cases for retention, export completeness and upload rollback."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class LifecycleTests(unittest.TestCase):
    def test_marker_cleanup_without_forcad_metadata(self):
        script = r'''
import io
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path('app').resolve()))
from app import create_app
from models import Shop, Catalog

app = create_app({'DATA_DIR': sys.argv[1], 'STAFF_PASSWORD': 'fixture', 'TESTING': True})
customer, staff = app.test_client(), app.test_client()
customer.post('/register', data={'username': 'fixture', 'password': 'long-fixture-password'})
customer.post('/login', data={'username': 'fixture', 'password': 'long-fixture-password'})
staff.post('/staff/login', data={'password': 'fixture'})
staff.post('/staff/vip/members', data={'username': 'fixture'})
customer.post('/login', data={'username': 'fixture', 'password': 'long-fixture-password'})

values = ['meko-' + 'a' * 20, 'MekoDataCTF{' + 'A' * 30 + '}', 'customer note meko-' + 'b' * 20,
          'MekoDataCTF{' + 'B' * 30 + '}', 'MekoDataCTF{' + 'C' * 30 + '}']
for index, value in enumerate(values):
    marker = index == 0
    note = customer.post('/account/notes', data={'collection_id': 1, 'note': value}).location
    assert value in customer.get(note).get_data(as_text=True)
    assert customer.get(note).status_code == (404 if marker else 200)

    customer.post('/cart/add/1', data={'quantity': 1})
    invoice = customer.post('/checkout', data={'memo': value}).location
    assert value in customer.get(invoice).get_data(as_text=True)
    again = customer.get(invoice)
    assert again.status_code == 200
    assert (value in again.get_data(as_text=True)) != marker

    offer = staff.post('/staff/vip', data={'code': value}).location
    offer = offer.replace('/staff/vip/offers/', '/member/offers/')
    assert value in customer.get(offer).get_data(as_text=True)
    assert customer.get(offer).status_code == (404 if marker else 200)

    staff.post('/staff/reconciliation', data={'value': value})
    assert value in staff.get('/exports/operations.sql').get_data(as_text=True)
    assert (value in staff.get('/exports/operations.sql').get_data(as_text=True)) != marker

    response = customer.post('/outfits/new', data={'manifest': (io.BytesIO(json.dumps({
        'preview_file': 'lookbook.txt', 'stylist_note': value}).encode()), 'outfit.json')})
    token = re.search(r'href="/outfits/([0-9a-f]{32})"', response.get_data(as_text=True))[1]
    assert value in customer.get('/outfits/' + token).get_data(as_text=True)
    assert customer.get('/outfits/' + token).status_code == (404 if marker else 200)
    if value.startswith('MekoDataCTF{'):
        preview = customer.post('/outfits/new', data={'manifest': (io.BytesIO(json.dumps({
            'preview_file': '../private/current.json'}).encode()), 'outfit.json')})
        assert preview.status_code == 200
        assert value in preview.get_data(as_text=True)
        app.config['PATCHED']['outfits'] = True
        blocked = customer.post('/outfits/new', data={'manifest': (io.BytesIO(json.dumps({
            'preview_file': '../private/current.json'}).encode()), 'outfit.json')})
        assert blocked.status_code == 400
        app.config['PATCHED']['outfits'] = False

with app.app_context():
    with Catalog() as db:
        assert db.connection.execute('SELECT count(*) FROM collection_notes').fetchone()[0] == 2
    with Shop() as db:
        assert db.connection.execute('SELECT count(*) FROM vip_offers').fetchone()[0] == 2
        assert db.connection.execute('SELECT count(*) FROM reconciliation_notes').fetchone()[0] == 2
        assert db.connection.execute('SELECT count(*) FROM orders WHERE memo LIKE ?', ('MekoDataCTF{%}',)).fetchone()[0] == 1
        assert db.connection.execute('SELECT count(*) FROM order_items i LEFT JOIN orders o ON o.id=i.order_id WHERE o.id IS NULL').fetchone()[0] == 0
    private = Path(sys.argv[1]) / 'simulation/private'
    flags = [json.loads(p.read_text()).get('stylist_note', '') for p in private.glob('*.json')]
    assert sum(v.startswith('MekoDataCTF{') for v in flags) == 1
    alias = private / 'current.json'
    alias.unlink()
    create_app({'DATA_DIR': sys.argv[1], 'STAFF_PASSWORD': 'fixture', 'TESTING': True})
    assert alias.is_file()

# A managed check keeps its marker until group cleanup so IDs cannot be reused
# under an outstanding checker_resources entry.
note = customer.post('/account/notes', data={'collection_id': 1, 'note': values[0]}).location
note_id = int(note.rsplit('/', 1)[1])
with app.app_context(), Shop() as db:
    db.connection.execute('INSERT INTO checker_groups(id,mode,run_id,tick,expires_tick) VALUES(?,?,?,?,?)', ('fixture-group', 'check', None, None, None))
    db.connection.execute('INSERT INTO checker_resources VALUES(?,?,?)', ('fixture-group', 'note', str(note_id)))
assert customer.get(note).status_code == 200
assert customer.get(note).status_code == 200
from lifecycle import prune
with app.app_context():
    assert prune({'check_group': 'fixture-group'})['deleted_groups'] == 1
assert customer.get(note).status_code == 404
'''
        with tempfile.TemporaryDirectory() as data:
            result = subprocess.run([sys.executable, '-c', script, data],
                                    cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_web_retention_and_upload_failures(self):
        script = r'''
import io
import json
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path('app').resolve()))
from app import create_app
from lifecycle import prune
from models import Shop
from models.outfits import OutfitStorage, StorageLimitReached

app = create_app({'DATA_DIR': sys.argv[1], 'STAFF_PASSWORD': 'fixture', 'TESTING': True})
data = Path(sys.argv[1])
client = app.test_client()
with app.app_context():
    with Shop() as db:
        db.connection.executemany('INSERT INTO reconciliation_notes(ref,value) VALUES(?,?)',
                                  [('ref-' + str(i), 'flag-' + str(i)) for i in range(151)])
    export = client.get('/exports/operations.sql').get_data(as_text=True)
    assert all("'flag-" + str(i) + "'" in export for i in range(151))
    with Shop() as db:
        for name, run, tick, expiry in [('old', 'a', 1, 4), ('live', 'a', 3, 6), ('other', 'b', 1, 2), ('legacy', None, None, None)]:
            db.connection.execute('INSERT INTO checker_groups(id,mode,run_id,tick,expires_tick) VALUES(?,?,?,?,?)', (name, 'put', run, tick, expiry))
            oid = db.connection.execute('INSERT INTO vip_offers(code) VALUES(?)', (name,)).lastrowid
            db.connection.execute('INSERT INTO checker_resources VALUES(?,?,?)', (name, 'offer', str(oid)))
    result = prune({'run_id': 'a', 'current_tick': 4, 'oldest_live_tick': 3})
    assert result['deleted_groups'] == 1
    with Shop() as db:
        assert {row[0] for row in db.connection.execute('SELECT code FROM vip_offers')} == {'live', 'other', 'legacy'}

client.post('/register', data={'username': 'fixture', 'password': 'long-fixture-password'})
client.post('/login', data={'username': 'fixture', 'password': 'long-fixture-password'})
def upload():
    return client.post('/outfits/new', data={'manifest': (io.BytesIO(json.dumps({
        'preview_file': 'lookbook.txt', 'stylist_note': 'private'}).encode()), 'outfit.json')})
def files():
    return {p for p in (data / 'simulation').rglob('*') if p.is_file()}
original = files()
with patch.object(OutfitStorage, 'save_note', side_effect=StorageLimitReached):
    assert upload().status_code == 507
assert files() == original
with patch.object(Shop, 'create_outfit', side_effect=sqlite3.OperationalError('fixture failure')):
    try:
        upload()
    except sqlite3.OperationalError:
        pass
    else:
        raise AssertionError('DB failure was not raised')
assert files() == original
with app.app_context(), Shop() as db:
    assert db.connection.execute('SELECT count(*) FROM outfits').fetchone()[0] == 0
'''
        with tempfile.TemporaryDirectory() as data:
            result = subprocess.run([sys.executable, '-c', script, data],
                                    cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
