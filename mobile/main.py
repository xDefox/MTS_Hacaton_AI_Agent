"""Точка входа Android APK (Flet). API — публичный URL бэкенда, не localhost."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

# Публичный API для телефона жюри (тот же host, что DEMO_WEB_URL / tunnel на :8000)
try:
    from api_defaults import DEFAULT_API_BASE
except ImportError:
    DEFAULT_API_BASE = "http://127.0.0.1:8000"

_api = (
    os.getenv("API_BASE")
    or os.getenv("DEMO_API_URL")
    or os.getenv("DEMO_WEB_URL")
    or DEFAULT_API_BASE
    or ""
).strip().rstrip("/")
if _api:
    os.environ["API_BASE"] = _api
    print(f"Mobile API_BASE={_api}")

import flet as ft

from frontend.app import main as app_main


def main(page: ft.Page):
    app_main(page)


ft.run(
    main,
    assets_dir=str(ROOT / "frontend" / "assets"),
)
