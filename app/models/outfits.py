"""Lưu manifest và ghi chú riêng của bộ phối đồ."""
import json
import os
import secrets
import threading
from pathlib import Path

from flask import current_app, g
from .flags import is_checker_marker, is_competition_flag

MAX_STORAGE_BYTES = 64 * 1024 * 1024
MAX_STORAGE_FILES = 4096
CURRENT_FLAG_ALIAS = 'current.json'
_storage_lock = threading.Lock()


class StorageLimitReached(Exception):
    """The bounded preview store has reached its per-service disk budget."""


def _write_bounded(path, content):
    encoded = content.encode("utf-8")
    with _storage_lock:
        files = [p for folder in (path.parent.parent / "designs", path.parent.parent / "private")
                 for p in folder.iterdir() if p.is_file()]
        used = sum(p.stat().st_size for p in files)
        if len(files) >= MAX_STORAGE_FILES or used + len(encoded) > MAX_STORAGE_BYTES:
            raise StorageLimitReached
        created = False
        try:
            with path.open("x", encoding="utf-8") as stream:
                created = True
                stream.write(content)
        except BaseException:
            if created:
                path.unlink(missing_ok=True)
            raise


class OutfitStorage:
    def __init__(self):
        self.root = Path(current_app.config["DATA_DIR"]) / "simulation"
        self.designs = self.root / "designs"
        self.private = self.root / "private"

    def save_manifest(self, content):
        path = self.designs / (secrets.token_hex(12) + ".json")
        _write_bounded(path, content)
        return path

    def save_note(self, user_id, name, note):
        token = secrets.token_hex(16)
        _write_bounded(self.private / (token + ".json"),
                       json.dumps({"user_id": user_id, "name": name, "stylist_note": note},
                                  ensure_ascii=False))
        return token

    def note_path(self, token):
        return self.private / (token + ".json")

    def publish_current(self, token):
        """Preserve team3's intentional traversal target, with atomic replacement."""
        content = json.dumps({'token': token})
        alias = self.private / CURRENT_FLAG_ALIAS
        with _storage_lock:
            files = [p for folder in (self.designs, self.private) for p in folder.iterdir()
                     if p.is_file() and p != alias]
            if len(files) + 1 > MAX_STORAGE_FILES or sum(p.stat().st_size for p in files) + len(content.encode()) > MAX_STORAGE_BYTES:
                raise StorageLimitReached
            temporary = self.private / (CURRENT_FLAG_ALIAS + '.' + secrets.token_hex(8) + '.tmp')
            try:
                temporary.write_text(content, encoding='utf-8')
                os.replace(temporary, alias)
            finally:
                temporary.unlink(missing_ok=True)

    def restore_current(self):
        from .shop import Shop
        with Shop() as db:
            active = db.connection.execute("SELECT o.note_token FROM checker_active a JOIN checker_resources r ON r.group_id=a.group_id AND r.kind='outfit' JOIN outfits o ON o.id=r.record WHERE a.task='upload'").fetchone()
        if active and self.note_path(active[0]).is_file():
            self.publish_current(active[0])
            return
        candidates = []
        for path in self.private.glob('*.json'):
            if path.name == CURRENT_FLAG_ALIAS:
                continue
            try:
                note = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(note, dict) and is_competition_flag(note.get('stylist_note')):
                    candidates.append((path.stat().st_mtime_ns, path.stem))
            except (ValueError, OSError):
                continue
        if candidates:
            self.publish_current(max(candidates)[1])
        else:
            (self.private / CURRENT_FLAG_ALIAS).unlink(missing_ok=True)

    def read_preview(self, target):
        if target != self.private / CURRENT_FLAG_ALIAS:
            return target.read_text(encoding='utf-8')
        alias = json.loads(target.read_text(encoding='utf-8'))
        token = alias.get('token')
        if not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
            raise FileNotFoundError('current flag unavailable')
        content = self.note_path(token).read_text(encoding='utf-8')
        if not is_competition_flag(json.loads(content).get('stylist_note')):
            raise FileNotFoundError('current flag unavailable')
        return content

    def expire_checker_marker_note(self, token):
        if g.get('checker_meta'):
            return
        with _storage_lock:
            path = self.note_path(token)
            try:
                stored = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                return
            if isinstance(stored, dict) and is_checker_marker(stored.get('stylist_note')):
                path.unlink(missing_ok=True)
