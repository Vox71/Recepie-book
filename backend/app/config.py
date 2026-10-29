"""Application settings.

All values come from environment variables only (CONTRIBUTION.md §2, §3).
No secret is hardcoded here: ``JWT_SECRET`` falls back to ``FLASK_SECRET_KEY``
and the application refuses to issue tokens when neither is set.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Mapping, Sequence

# openapi.yaml documents a 12 hour token lifetime for /login.
DEFAULT_JWT_TTL_HOURS = 12
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_DB_POOL_MIN = 1
DEFAULT_DB_POOL_MAX = 10
DEFAULT_RECOMMENDATIONS_LIMIT = 10
# The stub ML module answers with a shorter list: the diagram of ml_planning/ml_plan
# ends with "top-5 safe recipes", and KNN looks at this many neighbours.
DEFAULT_SMART_RECOMMENDATIONS_LIMIT = 5
DEFAULT_SMART_RECOMMENDATIONS_NEIGHBOURS = 10
DEFAULT_RATE_LIMIT_MAX_REQUESTS = 10
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_CORS_ORIGINS = ("*",)
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

Environ = Mapping[str, str]


def _as_bool(raw: str | None, default: bool) -> bool:
    """Convert a textual environment value into a boolean."""
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def _as_int(raw: str | None, default: int) -> int:
    """Convert a textual environment value into an integer, keeping the default on garbage."""
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_origins(raw: str | None) -> Sequence[str]:
    """Split a comma separated CORS allow-list into a sequence of origins."""
    if not raw or not raw.strip():
        return DEFAULT_CORS_ORIGINS
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


class Settings:
    """Configuration of a single application instance."""

    def __init__(self, environ: Environ | None = None) -> None:
        env: Environ = os.environ if environ is None else environ
        self.database_url = env.get("DATABASE_URL", "")
        self.jwt_secret = env.get("JWT_SECRET") or env.get("FLASK_SECRET_KEY") or ""
        self.jwt_algorithm = env.get("JWT_ALGORITHM") or DEFAULT_JWT_ALGORITHM
        self.jwt_ttl = timedelta(hours=_as_int(env.get("JWT_TTL_HOURS"), DEFAULT_JWT_TTL_HOURS))
        self.db_pool_min = _as_int(env.get("DB_POOL_MIN"), DEFAULT_DB_POOL_MIN)
        self.db_pool_max = _as_int(env.get("DB_POOL_MAX"), DEFAULT_DB_POOL_MAX)
        self.auto_init_schema = _as_bool(env.get("AUTO_INIT_SCHEMA"), True)
        self.cors_origins = _parse_origins(env.get("CORS_ORIGINS"))
        self.embeddings_enabled = _as_bool(env.get("EMBEDDINGS_ENABLED"), False)
        self.embedding_model = env.get("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
        self.recommendations_limit = _as_int(
            env.get("RECOMMENDATIONS_LIMIT"), DEFAULT_RECOMMENDATIONS_LIMIT
        )
        # Switch of the stub recommendation module (app/ml); off by default, so an
        # installation keeps the baseline scoring until the variable is set.
        self.smart_recommendations_enabled = _as_bool(
            env.get("SMART_RECOMMENDATIONS_ENABLED"), False
        )
        self.smart_recommendations_limit = _as_int(
            env.get("SMART_RECOMMENDATIONS_LIMIT"), DEFAULT_SMART_RECOMMENDATIONS_LIMIT
        )
        self.smart_recommendations_neighbours = _as_int(
            env.get("SMART_RECOMMENDATIONS_NEIGHBOURS"), DEFAULT_SMART_RECOMMENDATIONS_NEIGHBOURS
        )
        # Trained artifact of the v1 model (task 6.0). Empty means "the default path
        # app/ml/artifacts/v1.json"; a missing file keeps the bag-of-lemmas fallback.
        self.smart_recommendations_artifact = env.get("SMART_RECOMMENDATIONS_ARTIFACT", "")
        self.rate_limit_enabled = _as_bool(env.get("RATE_LIMIT_ENABLED"), False)
        self.rate_limit_max_requests = _as_int(
            env.get("RATE_LIMIT_MAX_REQUESTS"), DEFAULT_RATE_LIMIT_MAX_REQUESTS
        )
        self.rate_limit_window_seconds = _as_int(
            env.get("RATE_LIMIT_WINDOW_SECONDS"), DEFAULT_RATE_LIMIT_WINDOW_SECONDS
        )
        self.log_level = (env.get("LOG_LEVEL") or DEFAULT_LOG_LEVEL).upper()

    @classmethod
    def from_env(cls, environ: Environ | None = None) -> "Settings":
        """Build settings from ``environ`` (defaults to ``os.environ``)."""
        return cls(environ)

    def require_jwt_secret(self) -> str:
        """Return the JWT secret or fail loudly when it is not configured."""
        if not self.jwt_secret:
            raise RuntimeError("JWT_SECRET (or FLASK_SECRET_KEY) is not configured")
        return self.jwt_secret
