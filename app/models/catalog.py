"""Truy cập dữ liệu bộ sưu tập."""
from .database import Repository
from .flags import is_checker_marker, managed_resource, flagged_row_ids, delete_rows


class Catalog(Repository):
    database = 'catalog.sqlite3'

    def list_collections(self):
        return self.connection.execute('SELECT * FROM collections ORDER BY id')

    def collection_exists(self, parameters):
        return self.connection.execute('SELECT 1 FROM collections WHERE id=?', parameters)

    def create_note(self, parameters):
        return self.connection.execute('INSERT INTO collection_notes(user_id,collection_id,note) VALUES(?,?,?)', parameters)

    def expire_checker_marker(self, note_id):
        if managed_resource('note', note_id):
            return
        row = self.connection.execute('SELECT note FROM collection_notes WHERE id=?', (note_id,)).fetchone()
        if row and is_checker_marker(row['note']):
            self.connection.execute('DELETE FROM collection_notes WHERE id=?', (note_id,))

    def expire_flagged_notes(self, keep_id):
        delete_rows(self.connection, 'collection_notes', 'id',
                    flagged_row_ids(self.connection, 'collection_notes', 'id', 'note', keep_id))

    def list_customer_notes(self, parameters):
        return self.connection.execute('SELECT n.id,c.title FROM collection_notes n JOIN collections c ON c.id=n.collection_id WHERE n.user_id=? ORDER BY n.id DESC', parameters)

    def list_collection_options(self):
        return self.connection.execute('SELECT id,title FROM collections ORDER BY id')

    def find_note(self, parameters):
        return self.connection.execute('SELECT n.*,c.title FROM collection_notes n JOIN collections c ON c.id=n.collection_id WHERE n.id=?', parameters)

    def search(self, q, patched):
        if patched:
            sql = "SELECT id,title,description FROM collections WHERE title LIKE ?"
            rows = self.connection.execute(sql, ("%" + q + "%",)).fetchall()
        else:
            sql = "SELECT id,title,description FROM collections WHERE title LIKE '%" + q + "%'"
            rows = self.connection.execute(sql).fetchall()
        return rows
