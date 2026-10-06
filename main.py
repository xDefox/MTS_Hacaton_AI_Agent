"""Compatibility entrypoint for older run commands.

Prefer: uvicorn app.main:app --reload --port 8000
Also works: uvicorn main:app --reload --port 8000
"""

from app.main import app

__all__ = ["app"]
