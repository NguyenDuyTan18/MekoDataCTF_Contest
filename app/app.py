"""Khởi tạo và chạy ứng dụng Meko Boutique."""
import os
from pathlib import Path

from flask import Flask

from controllers import register_controllers
from models import initialize


def create_app(config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        DATA_DIR=Path(os.getenv("MEKO_DATA", "/var/lib/meko-boutique")),
        TEAM_ID=os.getenv("TEAM_ID", "team1"),
        STAFF_PASSWORD=os.getenv("MEKO_STAFF_PASSWORD", ""),
        MAX_CONTENT_LENGTH=256 * 1024,
    )
    app.config.update(config or {})
    initialize(app)
    register_controllers(app)
    return app


if __name__ == "__main__":
    from waitress import serve
    serve(create_app(), host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8080")))
