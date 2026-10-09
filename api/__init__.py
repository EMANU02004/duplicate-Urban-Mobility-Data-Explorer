"""Flask application factory."""
from __future__ import annotations

from pathlib import Path

from flask import Flask, g, jsonify

import config
from api.filters import BadRequest
from database.db import connect


def create_app(db_path: Path | str | None = None) -> Flask:
    app = Flask(__name__, static_folder=str(config.FRONTEND_DIR), static_url_path="")
    app.config["DB_PATH"] = Path(db_path or config.DB_PATH)
    app.json.sort_keys = False

    def get_db():
        if "db" not in g:
            if not app.config["DB_PATH"].exists():
                raise FileNotFoundError(
                    f"Database not found at {app.config['DB_PATH']}. Run `python -m pipeline.run` first.")
            g.db = connect(app.config["DB_PATH"], read_only=True)
        return g.db

    app.get_db = get_db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(BadRequest)
    def bad_request(err):
        return jsonify({"error": str(err)}), 400

    @app.errorhandler(FileNotFoundError)
    def no_database(err):
        return jsonify({"error": str(err)}), 503

    @app.errorhandler(404)
    def not_found(_err):
        return jsonify({"error": "not found"}), 404

    @app.after_request
    def cors(response):
        # Lets the dashboard call the API when opened from a separate static server.
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    from api.routes import bp
    app.register_blueprint(bp)
    return app
