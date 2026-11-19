"""Authenticated checker transactions, retry receipts and scoped garbage collection."""
import hmac
import json
from pathlib import Path

from flask import abort, g, request, current_app

from models.database import connect


def register(app):
    @app.before_request
    def checker_transaction():
        raw = request.headers.get('X-Meko-Lifecycle')
        if raw is None:
            return
        secret = app.config['STAFF_PASSWORD']
        signature = hmac.new(secret.encode(), raw.encode(), 'sha256').hexdigest()
        if not secret or not hmac.compare_digest(signature, request.headers.get('X-Meko-Signature', '')):
            abort(403)
        try:
            meta = json.loads(raw)
            if meta['mode'] not in ('check', 'put') or not isinstance(meta['group'], str):
                raise ValueError('metadata')
            if len(meta['group']) != 64 or any(c not in '0123456789abcdef' for c in meta['group']):
                raise ValueError('group')
            if meta.get('run_id') is not None:
                if (not isinstance(meta['run_id'], str) or not meta['run_id'] or
                        type(meta.get('tick')) is not int or type(meta.get('expires_tick')) is not int or
                        not 0 <= meta['tick'] < meta['expires_tick']):
                    raise ValueError('lifecycle')
        except (ValueError, KeyError, TypeError):
            abort(400)
        db = connect(Path(app.config['DATA_DIR']) / 'shop.sqlite3')
        g.checker_db, g.checker_meta = db, meta
        db.execute('ATTACH DATABASE ? AS catalog', (str(Path(app.config['DATA_DIR']) / 'catalog.sqlite3'),))
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM checker_retired WHERE group_id=?', (meta['group'],)).fetchone():
            abort(409)
        if meta['mode'] == 'put' and meta.get('run_id'):
            window = db.execute('SELECT current_tick,oldest_live_tick FROM checker_windows WHERE run_id=?', (meta['run_id'],)).fetchone()
            if window and meta['tick'] < window[1] and meta['expires_tick'] <= window[0]:
                abort(409)
        db.execute('INSERT OR IGNORE INTO checker_groups(id,mode,run_id,tick,expires_tick,task) VALUES(?,?,?,?,?,?)',
                   (meta['group'], meta['mode'], meta.get('run_id'), meta.get('tick'), meta.get('expires_tick'), meta.get('task')))
        saved = db.execute('SELECT mode,run_id,tick,expires_tick FROM checker_groups WHERE id=?', (meta['group'],)).fetchone()
        if tuple(saved) != (meta['mode'], meta.get('run_id'), meta.get('tick'), meta.get('expires_tick')):
            abort(409)
        if meta['mode'] == 'put' and request.method == 'POST' and request.path not in ('/login', '/staff/login') and not request.path.startswith('/cart/'):
            key = meta['group'] + ':' + request.path
            g.checker_receipt = key
            row = db.execute('SELECT status,headers,body FROM checker_receipts WHERE key=?', (key,)).fetchone()
            if row:
                return app.response_class(row['body'], status=row['status'], headers=json.loads(row['headers']))

    @app.after_request
    def checker_commit(response):
        db = g.get('checker_db')
        if db is not None:
            if response.status_code < 400:
                key = g.get('checker_receipt')
                if key:
                    db.execute('INSERT OR IGNORE INTO checker_receipts VALUES(?,?,?,?)',
                               (key, response.status_code, json.dumps(list(response.headers)), response.get_data()))
                db.commit()
                g.checker_committed = True
            else:
                db.rollback()
        return response

    @app.teardown_request
    def checker_close(error):
        db = g.pop('checker_db', None)
        if db is not None:
            db.close()
            if not g.get('checker_committed'):
                for path in g.get('checker_files', []):
                    path.unlink(missing_ok=True)
                if g.get('checker_files'):
                    from models.outfits import OutfitStorage
                    OutfitStorage().restore_current()

    @app.post('/staff/checker/cleanup')
    def cleanup():
        # Authorization uses the same staff secret, independent of customer sessions.
        secret = app.config['STAFF_PASSWORD']
        if not secret or not hmac.compare_digest(request.headers.get('X-Meko-Cleanup', ''), secret):
            abort(403)
        body = request.get_json()
        try:
            return prune(body)
        except (KeyError, TypeError, ValueError):
            abort(400)


def track(connection, kind, record):
    meta = g.get('checker_meta')
    if meta:
        connection.execute('INSERT OR IGNORE INTO checker_resources VALUES(?,?,?)',
                           (meta['group'], kind, str(record)))


def prune(body):
    data = Path(current_app.config['DATA_DIR'])
    db = connect(data / 'shop.sqlite3')
    files = []
    try:
        db.execute('ATTACH DATABASE ? AS catalog', (str(data / 'catalog.sqlite3'),))
        with db:
            db.execute('BEGIN IMMEDIATE')
            if 'check_group' in body:
                groups = db.execute("SELECT id FROM checker_groups WHERE id=? AND mode='check'", (body['check_group'],)).fetchall()
            elif 'discard_group' in body:
                groups = db.execute("SELECT id FROM checker_groups WHERE id=? AND mode='put' AND id NOT IN (SELECT group_id FROM checker_active)", (body['discard_group'],)).fetchall()
            elif 'activate_group' in body:
                group = body['activate_group']
                row = db.execute("SELECT task FROM checker_groups WHERE id=? AND mode='put'", (group,)).fetchone()
                if not row or row[0] not in ('idor', 'sqli', 'upload', 'jwt', 'backup'):
                    abort(400)
                task = row[0]
                groups = db.execute('SELECT group_id FROM checker_active WHERE task=? AND group_id<>?', (task, group)).fetchall()
                db.execute('INSERT INTO checker_active VALUES(?,?) ON CONFLICT(task) DO UPDATE SET group_id=excluded.group_id', (task, group))
            else:
                # ForcAD supplies a confirmed inclusive live window, scoped to one competition run.
                run, tick, oldest = body['run_id'], body['current_tick'], body['oldest_live_tick']
                if not isinstance(run, str) or not run or type(tick) is not int or type(oldest) is not int or not 0 <= oldest <= tick:
                    abort(400)
                db.execute('INSERT INTO checker_windows VALUES(?,?,?) ON CONFLICT(run_id) DO UPDATE SET current_tick=max(current_tick,excluded.current_tick),oldest_live_tick=max(oldest_live_tick,excluded.oldest_live_tick)', (run, tick, oldest))
                groups = db.execute("SELECT id FROM checker_groups WHERE mode='put' AND run_id=? AND tick<? AND expires_tick<=?",
                                    (run, oldest, tick)).fetchall()
            for group, in groups:
                resources = db.execute('SELECT kind,record FROM checker_resources WHERE group_id=?', (group,)).fetchall()
                customers = []
                for kind, record in resources:
                    if kind == 'customer':
                        customers.append(record)
                    elif kind == 'order':
                        db.execute('DELETE FROM order_items WHERE order_id=?', (record,))
                        db.execute('DELETE FROM orders WHERE id=?', (record,))
                    elif kind == 'outfit':
                        row = db.execute('SELECT manifest_file,note_token FROM outfits WHERE id=?', (record,)).fetchone()
                        if row:
                            files.extend([data / 'simulation' / 'designs' / row[0]] if row[0] else [])
                            files.extend([data / 'simulation' / 'private' / (row[1] + '.json')] if row[1] else [])
                        db.execute('DELETE FROM outfits WHERE id=?', (record,))
                    else:
                        table = {'note': 'collection_notes', 'offer': 'vip_offers', 'reconciliation': 'reconciliation_notes'}[kind]
                        db.execute('DELETE FROM ' + table + ' WHERE id=?', (record,))
                for uid in customers:
                    if not any(db.execute('SELECT 1 FROM ' + table + ' WHERE user_id=? LIMIT 1', (uid,)).fetchone()
                               for table in ('orders', 'outfits', 'collection_notes', 'saved_collection')):
                        db.execute('DELETE FROM customers WHERE id=?', (uid,))
                for path in files:
                    # A durable queue makes file deletion retryable after process/IO failures.
                    db.execute('INSERT OR IGNORE INTO checker_file_gc VALUES(?)', (str(path),))
                db.execute('DELETE FROM checker_resources WHERE group_id=?', (group,))
                db.execute('DELETE FROM checker_receipts WHERE key LIKE ?', (group + ':%',))
                db.execute('DELETE FROM checker_groups WHERE id=?', (group,))
                db.execute('DELETE FROM checker_active WHERE group_id=?', (group,))
                if 'activate_group' in body or 'run_id' in body:
                    db.execute('INSERT OR IGNORE INTO checker_retired VALUES(?)', (group,))
        for row in db.execute('SELECT path FROM checker_file_gc').fetchall():
            path = Path(row[0])
            if path.parent in (data / 'simulation' / 'designs', data / 'simulation' / 'private'):
                path.unlink(missing_ok=True)
                with db:
                    db.execute('DELETE FROM checker_file_gc WHERE path=?', (str(path),))
        from models.outfits import OutfitStorage
        OutfitStorage().restore_current()
        return {'ok': True, 'deleted_groups': len(groups)}
    finally:
        db.close()
