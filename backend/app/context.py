"""Accessors for the objects bound to the current application.

They live outside ``app/__init__.py`` so the API layer can import them without
creating a circular import with the application factory.
"""

from __future__ import annotations

from flask import Flask, current_app

from .config import Settings
from .db import Database


def get_db(app: Flask | None = None) -> Database:
    """Return the database facade of the given (or current) application."""
    target = app or current_app
    return target.extensions["db"]


def get_settings() -> Settings:
    """Return the settings of the current application."""
    return current_app.config["SETTINGS"]
