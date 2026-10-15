"""Flask application factory.

The factory pattern keeps configuration, database access and extensions inside
one application instance instead of module level globals (CONTRIBUTION.md §2).
"""

from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from .api import register_blueprints
from .config import Settings
from .context import get_db, get_settings
from .db import Database
from .errors import ApiError, register_error_handlers
from .security import InMemoryRateLimiter

__all__ = ["create_app", "get_db", "get_settings"]

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> Flask:
    """Build a Flask application instance."""
    app = Flask(__name__)
    app.config["SETTINGS"] = settings or Settings.from_env()
    app.json.sort_keys = False

    _configure_logging(app.config["SETTINGS"])
    CORS(app, resources={r"/*": {"origins": app.config["SETTINGS"].cors_origins}})

    app.extensions["db"] = Database(
        app.config["SETTINGS"].database_url,
        app.config["SETTINGS"].db_pool_min,
        app.config["SETTINGS"].db_pool_max,
    )
    app.extensions["rate_limiter"] = InMemoryRateLimiter(
        app.config["SETTINGS"].rate_limit_max_requests,
        app.config["SETTINGS"].rate_limit_window_seconds,
    )

    register_error_handlers(app)
    register_blueprints(app)

    if app.config["SETTINGS"].auto_init_schema:
        _ensure_schema(app)

    logger.info("Application created (database configured: %s)", get_db(app).is_configured)
    return app


def _ensure_schema(app: Flask) -> None:
    """Apply the schema at startup; a missing database must not crash the process."""
    try:
        get_db(app).ensure_schema()
    except ApiError as exc:
        logger.warning("Schema initialization skipped: %s", exc.message)


def _configure_logging(settings: Settings) -> None:
    """Apply the configured log level (``print`` is forbidden, CONTRIBUTION.md §8)."""
    level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger().setLevel(level)
