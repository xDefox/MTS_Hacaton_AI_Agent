"""Живой голосовой диалог внутри Flet: тот же mic+VAD+TTS, что на /call."""

from __future__ import annotations

import logging
import os
from typing import Callable
from urllib.parse import quote, urlparse

import flet as ft

from .phone_utils import format_phone, normalize_phone

logger = logging.getLogger(__name__)

try:
    import flet_webview as ftw

    _HAS_WEBVIEW = True
except ImportError:
    ftw = None  # type: ignore
    _HAS_WEBVIEW = False


def _page_origin(page: ft.Page, flet_port: int) -> str:
    """Origin страницы Flet — embed должен быть same-origin (микрофон)."""
    raw = (getattr(page, "url", None) or "").strip()
    if raw.startswith("http"):
        p = urlparse(raw)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}"
    host = (os.getenv("FLET_PUBLIC_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    return f"http://{host}:{flet_port}"


def embed_page_url(*, page: ft.Page, api_base: str, phone: str, flet_port: int) -> str:
    api = (api_base or "http://127.0.0.1:8000").rstrip("/")
    digits = normalize_phone(phone)
    q = f"phone={quote(digits)}&api={quote(api)}&back={quote('/')}"
    return f"{_page_origin(page, flet_port)}/live_call_embed.html?{q}"


class LiveCallController:
    """Вкладка «Звонок»: WebView с голосом (слушаю / отвечаю / говорю)."""

    def __init__(
        self,
        *,
        page: ft.Page,
        api_base: str,
        get_phone: Callable[[], str],
        colors: dict[str, str],
        flet_port: int | None = None,
    ) -> None:
        self.page = page
        self.api_base = api_base
        self.get_phone = get_phone
        self.colors = colors
        self.flet_port = int(flet_port or os.getenv("FLET_PORT") or "8550")
        self.active = False

        self.line_label = ft.Text("", size=12, color=colors["gray"])
        self.hint = ft.Text(
            "Живой диалог: слушаю → думаю → отвечаю голосом. Паузы и перебивание — как на /call.",
            size=12,
            color=colors["gray"],
        )
        self.status = ft.Text(
            "Нажмите «Позвонить голосом», разрешите микрофон и говорите.",
            size=13,
            color=colors["dark"],
        )
        self.start_btn = ft.FilledButton(
            "Позвонить голосом",
            icon=ft.Icons.PHONE_IN_TALK,
            bgcolor=colors["red"],
            color=colors["white"],
            height=48,
            on_click=self._open_fullscreen,
        )
        self._host = ft.Container(
            expand=True,
            height=520,
            border_radius=16,
            border=ft.Border.all(1, "#E8E8EA"),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Text("Загрузка…", color=colors["gray"]),
        )
        self.reload_btn = ft.TextButton(
            "Обновить панель",
            icon=ft.Icons.REFRESH,
            on_click=lambda e: self.refresh_line(reload=True),
        )
        self._column: ft.Column | None = None

    def _url(self) -> str:
        return embed_page_url(
            page=self.page,
            api_base=self.api_base,
            phone=self.get_phone(),
            flet_port=self.flet_port,
        )

    def _on_err(self, data) -> None:
        logger.warning("live embed error: %s", data)
        self.status.value = (
            f"Ошибка загрузки голосового UI: {data}. "
            "Попробуйте «На весь экран»."
        )
        try:
            self.page.update()
        except Exception:
            pass

    def _make_webview(self) -> ft.Control:
        if not _HAS_WEBVIEW:
            return ft.Column(
                [
                    ft.Text(
                        "Нужен пакет flet-webview для голосового UI.",
                        color=self.colors["red"],
                    ),
                    ft.Text("pip install flet-webview==0.86.5", size=12, color=self.colors["gray"]),
                    ft.FilledButton(
                        "Открыть голосовой звонок",
                        icon=ft.Icons.PHONE_IN_TALK,
                        on_click=self._open_fullscreen,
                    ),
                ],
                spacing=8,
            )
        return ftw.WebView(
            url=self._url(),
            expand=True,
            height=560,
            on_page_started=lambda e: logger.info("live embed loading"),
            on_web_resource_error=lambda e: self._on_err(getattr(e, "data", e)),
        )

    def _open_fullscreen(self, _=None) -> None:
        """Тот же UI на same-origin (микрофон надёжнее, чем в iframe WebView)."""
        url = self._url()
        try:
            # В браузере — эта же вкладка: полный mic+VAD+TTS как /call.
            if getattr(self.page, "web", False):
                self.page.launch_url(
                    url,
                    web_popup_window_name=ft.UrlTarget.SELF,
                )
            else:
                self.page.launch_url(url)
        except Exception as exc:
            self.status.value = f"Не удалось открыть: {exc}"
            try:
                self.page.update()
            except Exception:
                pass

    def build(self) -> ft.Control:
        self._host.content = self._make_webview()
        self._column = ft.Column(
            [
                ft.Text(
                    "Живой диалог",
                    size=18,
                    weight=ft.FontWeight.W_600,
                    color=self.colors["dark"],
                ),
                self.hint,
                self.line_label,
                self.status,
                self.start_btn,
                ft.Row([self.reload_btn], spacing=8),
                self._host,
            ],
            spacing=10,
            expand=True,
            tight=False,
        )
        return self._column

    def refresh_line(self, *, reload: bool = True) -> None:
        phone = normalize_phone(self.get_phone())
        self.line_label.value = (
            f"Линия: {format_phone(phone)}" if phone else "Сначала войдите с номером линии"
        )
        if reload:
            # На web смена url у WebView не всегда перезагружает iframe — пересоздаём.
            self._host.content = self._make_webview()
        try:
            self.page.update()
        except Exception:
            pass

    def hangup(self) -> None:
        self.refresh_line(reload=True)
