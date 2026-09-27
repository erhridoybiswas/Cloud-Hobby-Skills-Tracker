"""
Application factory and entrypoint.

Run locally with either:
    python backend/app.py
    python -m backend.app

The factory pattern (`create_app`) is what makes testing easy: each test
can build an isolated app with its own database and upload folder.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow `python backend/app.py` by putting the project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, jsonify, send_from_directory  # noqa: E402
from flask_cors import CORS  # noqa: E402

from backend.config import Config  # noqa: E402
from backend.middleware.error_handlers import register_error_handlers  # noqa: E402
from backend.routes import register_blueprints  # noqa: E402
from cloud.database_service import close_db, init_db, query_scalar  # noqa: E402
from cloud.storage_service import get_storage  # noqa: E402


def configure_logging(app: Flask) -> None:
    """Structured-ish logging that works both locally and on a cloud host."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    )
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)


def create_app(config_object=Config, overrides: dict | None = None) -> Flask:
    """Build and configure a Flask application instance."""
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_object)

    if overrides:
        app.config.update(overrides)

    # --- Extensions ---
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # --- Logging & errors ---
    configure_logging(app)
    register_error_handlers(app)

    # --- Database lifecycle ---
    init_db(app)                    # create tables if they do not exist
    app.teardown_appcontext(close_db)

    # --- Routes ---
    register_blueprints(app)

    # ---------------------------------------------------------------
    # Health check — used by load balancers and uptime monitors
    # ---------------------------------------------------------------
    @app.get("/api/health")
    def health():
        db_ok = True
        try:
            query_scalar("SELECT 1", default=1)
        except Exception:
            db_ok = False

        storage_ok = True
        try:
            get_storage()
        except Exception:
            storage_ok = False

        status = 200 if (db_ok and storage_ok) else 503
        return (
            jsonify(
                {
                    "status": "healthy" if status == 200 else "degraded",
                    "database": "up" if db_ok else "down",
                    "storage": "up" if storage_ok else "down",
                    "storage_backend": app.config.get("STORAGE_BACKEND", "local"),
                }
            ),
            status,
        )

    # ---------------------------------------------------------------
    # Frontend — served by the same process in local/simple deployments.
    # In cloud mode you would host /frontend on a CDN instead.
    # ---------------------------------------------------------------
    frontend_dir = Path(app.config["FRONTEND_DIR"])

    @app.get("/")
    def serve_index():
        return send_from_directory(frontend_dir, "index.html")

    @app.get("/<path:filename>")
    def serve_static(filename: str):
        # Never let the catch-all swallow unknown API routes
        if filename.startswith("api/"):
            return jsonify({"error": "The requested resource was not found."}), 404

        candidate = (frontend_dir / filename).resolve()
        if candidate.is_file() and str(candidate).startswith(str(frontend_dir.resolve())):
            return send_from_directory(frontend_dir, filename)

        return jsonify({"error": "The requested resource was not found."}), 404

    app.logger.info("Hobby & Skills Tracker started | storage=%s", app.config["STORAGE_BACKEND"])
    return app


# ---------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    import os

    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"

    print("\n" + "=" * 62)
    print("  Online Hobby & Skills Tracker — Cloud Computing Project")
    print("=" * 62)
    print(f"  Frontend + API : http://127.0.0.1:{port}")
    print(f"  Health check   : http://127.0.0.1:{port}/api/health")
    print(f"  Database       : {app.config['DATABASE_PATH']}")
    print(f"  Storage        : {app.config['STORAGE_BACKEND']} -> {app.config['UPLOAD_FOLDER']}")
    print("=" * 62 + "\n")

    app.run(host="0.0.0.0", port=port, debug=debug)