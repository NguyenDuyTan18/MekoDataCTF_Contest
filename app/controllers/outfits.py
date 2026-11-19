"""Controller outfits của cửa hàng."""
import json
import re
from pathlib import Path

from flask import abort, g, request, session

from models import Shop
from models.outfits import OutfitStorage, StorageLimitReached
from models.flags import is_competition_flag, managed_resource
from lifecycle import track, prune
from .common import page, patched, user_required


def register(app):
    @app.route("/outfits/new", methods=["GET", "POST"])
    @user_required
    def outfit_new():
        if request.method == "GET":
            return page("Tạo bộ phối đồ", form="outfit")
        # Nhận manifest JSON mô tả bộ phối và tệp xem trước.
        upload = request.files.get("manifest")
        if not upload or not upload.filename or Path(upload.filename).suffix.lower() != ".json":
            abort(400)
        raw = upload.read(65537)
        if len(raw) > 65536:
            abort(413)
        try:
            manifest = json.loads(raw)
        except (ValueError, UnicodeError):
            abort(400)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("preview_file"), str):
            abort(400)
        note = manifest.pop("stylist_note", None)
        if note is not None and (not isinstance(note, str) or not 1 <= len(note) <= 500):
            abort(400)
        storage = OutfitStorage()
        base = storage.designs.resolve()
        sandbox_root = storage.root.resolve()
        target = (base / manifest.get("preview_file", "")).resolve()
        if patched("outfits") and not target.is_relative_to(base):
            abort(400)
        # Tệp xem trước phải nằm trong vùng dữ liệu simulation.
        if not target.is_relative_to(sandbox_root) or not target.is_file():
            abort(400)
        name = str(manifest.get("name", "Bộ phối mới"))[:80]
        # Ghi chú stylist là dữ liệu riêng: không lưu vào designs hay bản manifest công khai.
        public_manifest = json.dumps(manifest, ensure_ascii=False)
        token = None
        manifest_path = None
        try:
            preview = storage.read_preview(target)
            manifest_path = storage.save_manifest(public_manifest)
            if g.get('checker_db') is not None:
                g.setdefault('checker_files', []).append(manifest_path)
            if note is not None:
                token = storage.save_note(session["uid"], name, note)
                if g.get('checker_db') is not None:
                    g.checker_files.append(storage.note_path(token))
            response = page("Bản phối đã lưu", preview_text=preview, outfit_token=token)
            with Shop() as db:
                cur = db.create_outfit((session["uid"], name, public_manifest))
                db.connection.execute('UPDATE outfits SET manifest_file=?,note_token=? WHERE id=?',
                                      (manifest_path.name, token, cur.lastrowid))
                track(db.connection, 'outfit', cur.lastrowid)
                if is_competition_flag(note):
                    if not g.get('checker_meta'):
                        for row in db.connection.execute('SELECT id,manifest_file,note_token FROM outfits WHERE id<>?', (cur.lastrowid,)).fetchall():
                            if not row['note_token'] or managed_resource('outfit', row['id']):
                                continue
                            old_path = storage.note_path(row['note_token'])
                            try:
                                old_note = json.loads(old_path.read_text(encoding='utf-8'))
                            except (ValueError, OSError):
                                continue
                            if is_competition_flag(old_note.get('stylist_note')):
                                paths = [old_path]
                                if row['manifest_file']:
                                    paths.append(storage.designs / row['manifest_file'])
                                db.connection.executemany('INSERT OR IGNORE INTO checker_file_gc VALUES(?)', [(str(p),) for p in paths])
                                db.connection.execute('DELETE FROM outfits WHERE id=?', (row['id'],))
                    storage.publish_current(token)
            if not g.get('checker_meta'):
                prune({'check_group': ''})
            return response
        except BaseException as exc:
            if manifest_path:
                manifest_path.unlink(missing_ok=True)
            if token:
                storage.note_path(token).unlink(missing_ok=True)
            storage.restore_current()
            if isinstance(exc, StorageLimitReached):
                return 'Outfit storage limit reached', 507
            raise


    @app.get("/outfits/<token>")
    @user_required
    def outfit_detail(token):
        path = OutfitStorage().note_path(token)
        if not re.fullmatch(r"[0-9a-f]{32}", token) or not path.is_file():
            abort(404)
        outfit = json.loads(path.read_text(encoding="utf-8"))
        if outfit["user_id"] != session["uid"]:
            abort(403)
        response = page(outfit["name"], outfit=outfit)
        OutfitStorage().expire_checker_marker_note(token)
        return response

