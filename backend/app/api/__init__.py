"""HTTP layer: one blueprint per API area (paths mirror openapi.yaml)."""

from __future__ import annotations

from flask import Flask

from . import auth, favorites, fridge, notifications, recommendations, recipes, system, users

BLUEPRINTS = (
    system.bp,
    auth.bp,
    users.bp,
    recipes.bp,
    favorites.bp,
    fridge.bp,
    notifications.bp,
    recommendations.bp,
)


def register_blueprints(app: Flask) -> None:
    """Register every API blueprint on the application."""
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
