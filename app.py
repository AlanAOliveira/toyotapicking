"""Toyota Picking — Flask application entry point."""
import os
import logging
from flask import Flask
from config import Config

log = logging.getLogger(__name__)


def create_app(config_class: type = Config) -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Register blueprints
    from routes.main import main_bp
    from routes.picking import picking_bp
    from routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(picking_bp, url_prefix="/picking")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Initialize Lakebase schema at startup.
    # Failure is logged but doesn't crash the app — the pick-list read path
    # doesn't need Lakebase, only the status feature does. This lets the app
    # keep serving read-only picking screens even if Lakebase is unreachable.
    try:
        from database.lakebase_schema import init_lakebase_schema
        init_lakebase_schema()
    except Exception as e:
        log.exception("Lakebase schema init failed: %s", e)

    return app


app = create_app()
app.config["VERSION"] = os.environ.get(
    "APP_VERSION", "dev-" + str(int(__import__("time").time()))
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)