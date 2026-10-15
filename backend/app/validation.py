"""Input validation helpers (CONTRIBUTION.md §5).

Every value coming from a client passes through these functions; failures raise
``BadRequest`` which the API layer renders as HTTP 400 with ``{"error": ...}``.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Sequence

from flask import request

from .errors import BadRequest

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
MAX_SHORT_FIELD_LENGTH = 255
MAX_TEXT_FIELD_LENGTH = 10000
MAX_LIST_LENGTH = 100
MIN_PASSWORD_LENGTH = 8


def json_object_body() -> dict:
    """Return the request body as a JSON object or fail with 400."""
    payload = request.get_json(silent=True)
    if payload is None:
        raise BadRequest("Request body must be a valid JSON object")
    if not isinstance(payload, dict):
        raise BadRequest("Request body must be a JSON object")
    return payload


def json_array_body() -> list:
    """Return the request body as a JSON array or fail with 400."""
    payload = request.get_json(silent=True)
    if payload is None:
        raise BadRequest("Request body must be a valid JSON array")
    if not isinstance(payload, list):
        raise BadRequest("Request body must be a JSON array")
    return payload


def require_string(
    data: dict,
    field: str,
    *,
    max_length: int = MAX_SHORT_FIELD_LENGTH,
    min_length: int = 1,
) -> str:
    """Return a non-empty trimmed string field."""
    value = data.get(field)
    if value is None:
        raise BadRequest(f"Field '{field}' is required")
    if not isinstance(value, str):
        raise BadRequest(f"Field '{field}' must be a string")
    value = value.strip()
    if len(value) < min_length:
        raise BadRequest(f"Field '{field}' must be at least {min_length} characters long")
    if len(value) > max_length:
        raise BadRequest(f"Field '{field}' must be at most {max_length} characters long")
    return value


def optional_string(
    data: dict, field: str, *, max_length: int = MAX_TEXT_FIELD_LENGTH
) -> str | None:
    """Return an optional trimmed string field."""
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BadRequest(f"Field '{field}' must be a string")
    value = value.strip()
    if len(value) > max_length:
        raise BadRequest(f"Field '{field}' must be at most {max_length} characters long")
    return value or None


def require_email(data: dict, field: str = "email") -> str:
    """Return a normalized e-mail address."""
    value = require_string(data, field, max_length=MAX_SHORT_FIELD_LENGTH).lower()
    if not EMAIL_PATTERN.match(value):
        raise BadRequest("Field 'email' must be a valid e-mail address")
    return value


def require_positive_int(data: dict, field: str) -> int:
    """Return an integer field greater than zero (booleans are rejected)."""
    value = data.get(field)
    if value is None:
        raise BadRequest(f"Field '{field}' is required")
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadRequest(f"Field '{field}' must be an integer")
    if value <= 0:
        raise BadRequest(f"Field '{field}' must be greater than zero")
    return value


def require_positive_number(data: dict, field: str) -> float:
    """Return a positive numeric field (integers and floats are accepted)."""
    value = data.get(field)
    if value is None:
        raise BadRequest(f"Field '{field}' is required")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BadRequest(f"Field '{field}' must be a number")
    if value <= 0:
        raise BadRequest(f"Field '{field}' must be greater than zero")
    return float(value)


def require_list_of_terms(data: dict, field: str, *, required: bool = True) -> list[str]:
    """Return a list of non-empty strings for the given field."""
    value = data.get(field)
    if value is None:
        if required:
            raise BadRequest(f"Field '{field}' is required")
        return []
    if not isinstance(value, list):
        raise BadRequest(f"Field '{field}' must be an array of strings")
    if len(value) > MAX_LIST_LENGTH:
        raise BadRequest(f"Field '{field}' must contain at most {MAX_LIST_LENGTH} items")
    terms: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise BadRequest(f"Field '{field}' must contain only strings")
        item = item.strip()
        if not item:
            raise BadRequest(f"Field '{field}' must not contain empty values")
        if len(item) > MAX_SHORT_FIELD_LENGTH:
            raise BadRequest(
                f"Items of '{field}' must be at most {MAX_SHORT_FIELD_LENGTH} characters long"
            )
        terms.append(item)
    return terms


def parse_terms(value: Any) -> list[str]:
    """Normalize a stored ``allergies``/``preferences`` value into a list of terms.

    ``/register`` stores whatever the client sent ("as is" per openapi.yaml), so a
    stored value may be a list, a comma separated string, a mapping or ``None``.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    if isinstance(value, dict):
        return [str(key).strip() for key in value if str(key).strip()]
    return [str(value)]


def has_any_term(haystack: str, terms: Sequence[str]) -> bool:
    """True when ``haystack`` contains at least one of ``terms`` (case-insensitive)."""
    lowered = haystack.lower()
    return any(term.lower() in lowered for term in terms if term)


def require_date(data: dict, field: str) -> date:
    """Return an ISO 8601 (``YYYY-MM-DD``) date field."""
    value = data.get(field)
    if value is None:
        raise BadRequest(f"Field '{field}' is required")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise BadRequest(f"Field '{field}' must be a date in ISO 8601 format")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise BadRequest(f"Field '{field}' must be a date in ISO 8601 format") from exc
