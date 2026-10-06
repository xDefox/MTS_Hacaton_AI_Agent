"""Compatibility entrypoint.

Prefer: uvicorn backend.main:app --reload --port 8000
Also works: uvicorn main:app --reload --port 8000
"""

from backend.main import app

__all__ = ["app"]
