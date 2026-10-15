"""WSGI entry point.

Production: ``gunicorn main:app`` (see backend/Dockerfile).
Local development: ``python main.py``.
"""

from __future__ import annotations

from dotenv import load_dotenv

from app import create_app

load_dotenv()  # .env is optional: real deployments pass environment variables

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)  # noqa: S104 - inside the container this is expected
