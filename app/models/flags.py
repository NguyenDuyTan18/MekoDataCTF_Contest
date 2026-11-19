"""Recognize the temporary marker used by the functional checker."""
import re
from pathlib import Path

from flask import current_app, g

from .database import connect


_CHECKER_MARKER = re.compile(r"meko-[a-f0-9]{20}\Z")
_COMPETITION_FLAG = re.compile(r"MekoDataCTF\{[A-Z0-9]{30}\}\Z")


def is_competition_flag(value):
    return isinstance(value, str) and _COMPETITION_FLAG.fullmatch(value) is not None


def flagged_row_ids(connection, table, id_column, value_column, keep_id):
    # Managed PUTs retire the whole previous group after verification instead.
    if g.get('checker_meta'):
        return []
    kind = {'orders': 'order', 'collection_notes': 'note', 'vip_offers': 'offer',
            'reconciliation_notes': 'reconciliation'}[table]
    ids = []
    for row in connection.execute(f'SELECT id,{id_column},{value_column} FROM {table}'):
        if row[1] != keep_id and is_competition_flag(row[2]) and not managed_resource(kind, row[0]):
            ids.append(row[1])
    return ids


def delete_rows(connection, table, id_column, row_ids):
    connection.executemany(f'DELETE FROM {table} WHERE {id_column}=?', [(row,) for row in row_ids])


def is_checker_marker(value):
    return isinstance(value, str) and _CHECKER_MARKER.fullmatch(value) is not None


def managed_resource(kind, record):
    """Managed checks delete resources together, after their final assertion.

    Early deletion could let SQLite reuse an ID before group cleanup, causing
    cleanup to remove another request's new record.
    """
    if g.get('checker_meta'):
        return True
    db = connect(Path(current_app.config['DATA_DIR']) / 'shop.sqlite3')
    try:
        return db.execute('SELECT 1 FROM checker_resources WHERE kind=? AND record=? LIMIT 1',
                          (kind, str(record))).fetchone() is not None
    finally:
        db.close()
