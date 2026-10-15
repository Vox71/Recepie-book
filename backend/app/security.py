"""JWT helpers, the ``token_required`` decorator and a small rate limiter."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Deque, TypeVar

import jwt
from flask import current_app, g, request

from .config import Settings
from .errors import TooManyRequests, Unauthorized

logger = logging.getLogger(__name__)

BEARER_PREFIX = "bearer "
F = TypeVar("F", bound=Callable)


def get_settings() -> Settings:
    """Return the settings of the current application."""
    return current_app.config["SETTINGS"]


def create_access_token(user_id: int, extra_claims: dict | None = None) -> str:
    """Issue a signed access token for ``user_id`` (lifetime from settings)."""
    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + settings.jwt_ttl,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.require_jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Validate ``token`` and return its claims; raises ``jwt.InvalidTokenError``."""
    settings = get_settings()
    return jwt.decode(token, settings.require_jwt_secret(), algorithms=[settings.jwt_algorithm])


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith(BEARER_PREFIX):
        return None
    token = header[len(BEARER_PREFIX) :].strip()
    return token or None


def token_required(view: F) -> F:
    """Reject the request with 401 unless a valid ``Bearer`` token is present."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        if token is None:
            raise Unauthorized("Authorization token is missing")
        try:
            claims = decode_access_token(token)
            user_id = int(claims["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            logger.info("Rejected token: %s", type(exc).__name__)
            raise Unauthorized("Authorization token is invalid or expired") from exc
        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def current_user_id() -> int:
    """Return the user id extracted from the token by ``token_required``."""
    user_id = getattr(g, "user_id", None)
    if user_id is None:
        raise Unauthorized("Authorization token is missing")
    return user_id


class InMemoryRateLimiter:
    """Sliding-window limiter keeping counters in the current process.

    It protects ``/login`` and ``/register`` from brute force attempts
    (CONTRIBUTION.md §3).  State lives in the application instance, not in a
    module level global.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Register a hit for ``key`` or raise ``TooManyRequests``."""
        if self._max_requests <= 0:
            return
        now = time.monotonic()
        threshold = now - self._window_seconds
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= threshold:
                hits.popleft()
            if len(hits) >= self._max_requests:
                raise TooManyRequests("Too many requests, try again later")
            hits.append(now)


def _client_key() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit(bucket: str) -> Callable[[F], F]:
    """Apply the process-local limiter per client IP for the given ``bucket``."""

    def decorator(view: F) -> F:
        @wraps(view)
        def wrapper(*args, **kwargs):
            settings = get_settings()
            limiter = current_app.extensions.get("rate_limiter")
            if settings.rate_limit_enabled and limiter is not None:
                limiter.check(f"{bucket}:{_client_key()}")
            return view(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
