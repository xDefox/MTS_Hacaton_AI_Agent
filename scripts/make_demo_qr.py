"""QR на лёгкий веб МТС (uvicorn :8000 /app) → docs/demo_qr.png

Не Flet :8550 — Flutter JS ~10MB, на мобильном LTE белый экран минутами.
Не Telegram-бот — бот только по личному ключу из приложения.

  uvicorn backend.main:app --port 8000
  cloudflared tunnel --url http://127.0.0.1:8000
  set DEMO_WEB_URL=https://xxxx.trycloudflare.com
  python scripts/make_demo_qr.py
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_M

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo_qr.png"


def _is_lan(ip: str) -> bool:
    if ip.startswith("127.") or ip.startswith("169.254."):
        return False
    if ip.startswith("192.168."):
        return True
    if ip.startswith("172."):
        try:
            second = int(ip.split(".")[1])
        except (IndexError, ValueError):
            return False
        return 16 <= second <= 31
    if ip.startswith("10."):
        parts = ip.split(".")
        if len(parts) >= 2 and parts[1] in {"8", "9", "255"}:
            return False
        return True
    return False


def local_ip() -> str:
    env = (os.getenv("DEMO_HOST") or "").strip()
    if env:
        return env
    candidates: list[str] = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        candidates.append(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        sock.close()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in candidates:
                candidates.append(ip)
    except OSError:
        pass
    for ip in candidates:
        if _is_lan(ip):
            return ip
    for ip in candidates:
        if not ip.startswith("127."):
            return ip
    return "127.0.0.1"


def demo_url() -> str:
    """Только URL Flet-веба (МТС UI)."""
    override = (os.getenv("DEMO_WEB_URL") or "").strip().rstrip("/")
    if override:
        low = override.lower()
        if "t.me/" in low or "telegram" in low:
            raise ValueError(
                "DEMO_WEB_URL указывает на Telegram — нужен URL Flet "
                "(например https://….trycloudflare.com или http://192.168.x.x:8550)"
            )
        if override.startswith("http://127.") or "localhost" in low:
            print(
                "WARNING: localhost в DEMO_WEB_URL — с телефона жюри не откроется.",
                file=sys.stderr,
            )
        return override

    port = (os.getenv("DEMO_PORT") or "8000").strip()
    url = f"http://{local_ip()}:{port}/app"
    print(
        f"DEMO_WEB_URL не задан — QR на LAN лёгкий веб: {url}\n"
        "Для жюри: cloudflared tunnel --url http://127.0.0.1:8000 "
        "и DEMO_WEB_URL=https://…",
        file=sys.stderr,
    )
    return url


def build_qr(url: str | None = None) -> tuple[Path, str]:
    url = url or demo_url()
    img = qrcode.make(
        url,
        error_correction=ERROR_CORRECT_M,
        box_size=12,
        border=2,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    return OUT, url


if __name__ == "__main__":
    path, url = build_qr()
    print(f"QR -> {path}")
    print(f"URL -> {url}")
    print("Target: light MTS web /app on uvicorn (not Flet, not bot).")
