"""Lưu manifest và ghi chú riêng của bộ phối đồ."""
import json
import secrets
from pathlib import Path

from flask import current_app


class OutfitStorage:
    def __init__(self):
        self.root = Path(current_app.config["DATA_DIR"]) / "simulation"
        self.designs = self.root / "designs"
        self.private = self.root / "private"

    def save_manifest(self, content):
        (self.designs / (secrets.token_hex(12) + ".json")).write_text(
            content, encoding="utf-8")

    def save_note(self, user_id, name, note):
        token = secrets.token_hex(16)
        (self.private / (token + ".json")).write_text(
            json.dumps({"user_id": user_id, "name": name, "stylist_note": note},
                       ensure_ascii=False), encoding="utf-8")
        return token

    def note_path(self, token):
        return self.private / (token + ".json")
