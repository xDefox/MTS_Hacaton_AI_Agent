"""Страница подключения услуги «ИИ-агент для звонков».

Flet 0.86 · стиль МТС · адаптив под десктоп, планшеты и мобильные экраны.

Запуск:  python -m frontend.app
"""

import os
import threading
import time
import webbrowser

import flet as ft
import httpx

from backend.services.telegram_notify import format_phone, normalize_phone

from .assests import (
    MTS_RED,
    MTS_RED_DARK,
    MTS_DARK,
    MTS_GRAY,
    MTS_BG,
    MTS_WHITE,
    SERVICE_NAME,
    HEADER_CONNECT_SUBTITLE,
    SERVICE_TAGLINE,
    SERVICE_ICON,
    SERVICE_DESCRIPTION,
    SERVICE_FEATURES,
    CONNECT_BUTTON_TEXT,
    MORE_BUTTON_TEXT,
    LOGIN_TITLE,
    LOGIN_HINT,
    LOGIN_BUTTON_TEXT,
    CONSENT_TEXT,
    CONSENT_DOCS,
    TELEGRAM_OPEN_TEXT,
    TELEGRAM_TOGGLE_HINT,
    TELEGRAM_BOT_URL,
    FEATURES_TITLE,
    FEATURES,
    ROUTING_TITLE,
    ROUTING_VOICE_LABEL,
    ROUTING_CHAT_LABEL,
    CONNECTED_STATUS,
    DISCONNECT_BUTTON_TEXT,
    OPEN_BUTTON_TEXT,
    CATALOG_TITLE,
    AVAILABLE_TITLE,
    CONNECTED_SECTION_TITLE,
    EMPTY_CONNECTED,
    PROFILE_LABEL,
    EXTRA_SERVICE_NAME,
    EXTRA_SERVICE_TAGLINE,
    EXTRA_SERVICE_ICON,
    EXTRA_BUTTON_TEXT,
)

CARD_SIZE = 280            # карточка на десктопе
MOBILE_BREAKPOINT = 640    # ниже — маленький экран (телефон)
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
MOBILE_PLATFORMS = {
    ft.PagePlatform.ANDROID,
    ft.PagePlatform.IOS,
    ft.PagePlatform.ANDROID_TV,
}


def _square_checkbox(**kwargs) -> ft.Checkbox:
    """Квадратный пустой чекбокс (не кружок Material 3)."""
    return ft.Checkbox(
        shape=ft.RoundedRectangleBorder(radius=2),
        border_side=ft.BorderSide(1.5, MTS_GRAY),
        fill_color={
            ft.ControlState.DEFAULT: MTS_WHITE,
            ft.ControlState.SELECTED: MTS_RED,
        },
        check_color=MTS_WHITE,
        active_color=MTS_RED,
        **kwargs,
    )


def main(page: ft.Page):
    page.title = "МТС — Подключение услуги"
    page.bgcolor = MTS_BG
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.theme = ft.Theme(
        checkbox_theme=ft.CheckboxTheme(
            shape=ft.RoundedRectangleBorder(radius=2),
        ),
    )

    # Размер окна задаём только на десктопе: на мобильных размерами
    # управляет система, а на маленьких экранах фиксированный размер — баг.
    if getattr(page, "platform", None) not in MOBILE_PLATFORMS:
        page.window.width = 1100
        page.window.height = 720

    connected_phone = {"value": ""}
    service_on = {"value": False}
    tg_on = {"value": False}
    login_phone = ft.TextField(
        label="Номер телефона",
        hint_text="+7 900 123-45-67",
        dense=True,
        width=280,
    )
    login_error = ft.Text(
        "Введите номер телефона",
        size=12,
        color=MTS_RED,
        visible=False,
        width=280,
        text_align=ft.TextAlign.CENTER,
    )

    # --- Обработчики (объявлены до использования в диалоге) ---------------
    def enter_app(_=None):
        """Заглушка входа в приложение МТС: номер уже «из профиля»."""
        phone = normalize_phone(login_phone.value or "")
        if len(phone) < 10:
            login_error.visible = True
            page.update()
            return
        login_error.visible = False
        connected_phone["value"] = phone
        try:
            httpx.post(
                f"{API_BASE}/api/v1/telegram/register",
                json={"phone": phone},
                timeout=3.0,
            )
        except httpx.RequestError:
            pass
        profile_phone.value = format_phone(phone)
        profile_chip.visible = True
        _show_catalog()

    def close_dialog(_=None):
        pop = getattr(page, "pop_dialog", None)
        if callable(pop) and details_dialog.open:
            pop()
        else:
            details_dialog.open = False
        page.update()

    def open_details(_=None):
        """Повторно открыть то же окно: Flet 0.90 держит его в стеке после закрытия."""
        stacked = details_dialog in getattr(
            getattr(page, "_dialogs", None), "controls", []
        )
        if stacked or details_dialog.open:
            details_dialog.open = True
            page.update()
            return
        try:
            page.show_dialog(details_dialog)
        except RuntimeError:
            details_dialog.open = True
        page.update()

    def connect_service(_=None):
        if not consent_checkbox.value:
            consent_checkbox.error = True
            consent_error.visible = True
            page.update()
            return
        phone = connected_phone["value"]
        if len(phone) < 10:
            page.update()
            return
        consent_checkbox.error = False
        consent_error.visible = False
        try:
            httpx.post(
                f"{API_BASE}/api/v1/telegram/register",
                json={"phone": phone},
                timeout=3.0,
            )
        except httpx.RequestError:
            pass
        close_dialog()
        service_on["value"] = True
        _open_settings(reset_tg=not tg_on["value"])
        _start_poll()

    def open_connected(_=None):
        """Уже подключена — сразу в настройки, без повторного «Подключить»."""
        _open_settings(reset_tg=False)

    def _sync_catalog_cards():
        on = service_on["value"]
        service_card.visible = not on
        connected_card.visible = on
        connected_empty.visible = not on

    def _show_catalog():
        login_gate.visible = False
        login_wrap.visible = False
        catalog.visible = True
        features_panel.visible = False
        back_btn.visible = False
        extra_card.visible = True
        _sync_catalog_cards()
        header_subtitle.value = f"| {CATALOG_TITLE}"
        page.title = "МТС — Услуги"
        page.update()

    def _open_settings(*, reset_tg: bool):
        phone = connected_phone["value"]
        header_subtitle.value = f"| {SERVICE_NAME}"
        page.title = f"МТС — {SERVICE_NAME}"
        login_gate.visible = False
        login_wrap.visible = False
        catalog.visible = False
        features_panel.visible = True
        back_btn.visible = True
        if reset_tg:
            tg_on["value"] = False
            tg_on["stop"] = False
            tg_active.value = False
            tg_status_text.value = f"Ожидает /start · {format_phone(phone)}"
            tg_status_text.color = MTS_GRAY
        page.update()

    def go_catalog(_=None):
        """Стрелка назад: услуга остаётся подключённой."""
        _show_catalog()

    def disconnect_service(_=None):
        """Снять услугу: вернуть карточку в «Доступные»."""
        tg_on["stop"] = True
        tg_on["polling"] = False
        tg_on["value"] = False
        tg_active.value = False
        tg_status_text.value = "После /start в боте здесь загорится «Активировано»"
        tg_status_text.color = MTS_GRAY
        service_on["value"] = False
        phone = connected_phone["value"]
        try:
            if phone:
                httpx.post(
                    f"{API_BASE}/api/v1/telegram/deactivate",
                    json={"phone": phone},
                    timeout=3.0,
                )
        except httpx.RequestError:
            pass
        _show_catalog()

    def _bot_start_url(phone: str) -> str:
        digits = normalize_phone(phone)
        base = TELEGRAM_BOT_URL.rstrip("/")
        return f"{base}?start={digits}" if digits else base

    def open_telegram(_=None):
        """Один переход: без url= на кнопке, иначе Flet открывает ссылку дважды."""
        url = _bot_start_url(connected_phone["value"])
        if not hasattr(page, "session"):
            page.launch_url(url)
            return
        webbrowser.open(url)

    # --- Согласие, Telegram-бот и кнопка подключения ---------------------
    def on_consent_change(e):
        """Кнопка «Подключить» тухнет, пока не принята оферта."""
        agreed = bool(e.control.value)
        connect_btn.opacity = 1.0 if agreed else 0.4
        if agreed:
            consent_checkbox.error = False
            consent_error.visible = False
        page.update()

    consent_checkbox = _square_checkbox(
        value=False,
        on_change=on_consent_change,
    )
    consent_error = ft.Text(
        "Подтвердите согласие, чтобы подключить услугу",
        size=12,
        color=MTS_RED,
        visible=False,
    )
    consent_row = ft.Row(
        [
            consent_checkbox,
            ft.Text(CONSENT_TEXT, size=13, color=MTS_DARK, expand=True),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    connect_btn = ft.FilledButton(
        CONNECT_BUTTON_TEXT,
        opacity=0.4,  # «тухнет», пока не принята оферта
        animate_opacity=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        style=ft.ButtonStyle(
            bgcolor=MTS_RED,
            overlay_color=MTS_RED_DARK,
            color=MTS_WHITE,
        ),
        on_click=lambda e: connect_service(e),
    )

    # --- Окно «Подробнее» -----------------------------------------------
    dialog_box = ft.Container(
        width=420,
        content=ft.Column(
            [
                ft.Text(
                    SERVICE_DESCRIPTION,
                    size=15,
                    color=MTS_DARK,
                    selectable=True,
                ),
                ft.Text(
                    "Что входит в услугу:",
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=MTS_DARK,
                ),
                *[
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK, color=MTS_RED, size=18),
                            ft.Text(f, size=14, color=MTS_DARK, expand=True),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    )
                    for f in SERVICE_FEATURES
                ],
                ft.Divider(height=1, color="#E8E8EA"),
                consent_row,
                consent_error,
                ft.Text(
                    CONSENT_DOCS,
                    size=12,
                    color=MTS_GRAY,
                ),
            ],
            spacing=12,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    details_dialog = ft.AlertDialog(
        modal=True,
        bgcolor=MTS_WHITE,
        title=ft.Text(
            SERVICE_NAME,
            size=22,
            weight=ft.FontWeight.BOLD,
            color=MTS_DARK,
        ),
        content=dialog_box,
        actions=[
            ft.TextButton(
                "Закрыть",
                style=ft.ButtonStyle(color=MTS_GRAY),
                on_click=lambda e: close_dialog(),
            ),
            connect_btn,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _catalog_card(*, icon: str, title: str, tagline: str, action, header_bg: str):
        icon_box = ft.Container(
            height=88,
            bgcolor=header_bg,
            border_radius=ft.BorderRadius(
                top_left=24,
                top_right=24,
                bottom_left=0,
                bottom_right=0,
            ),
            alignment=ft.Alignment.CENTER,
            content=ft.Text(icon, size=40),
        )
        card = ft.Container(
            width=CARD_SIZE,
            border_radius=24,
            bgcolor=MTS_WHITE,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=18,
                color="#1D1D1B22",
                offset=ft.Offset(0, 6),
            ),
            border=ft.Border.all(1, "#E8E8EA"),
            content=ft.Column(
                [
                    icon_box,
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
                        content=ft.Column(
                            [
                                ft.Text(
                                    title,
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=MTS_DARK,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    tagline,
                                    size=12,
                                    color=MTS_GRAY,
                                    max_lines=2,
                                ),
                                action,
                            ],
                            spacing=10,
                            alignment=ft.MainAxisAlignment.START,
                            horizontal_alignment=ft.CrossAxisAlignment.START,
                            tight=True,
                        ),
                    ),
                ],
                spacing=0,
                tight=True,
            ),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        return icon_box, card

    more_button = ft.FilledButton(
        MORE_BUTTON_TEXT,
        style=ft.ButtonStyle(
            bgcolor=MTS_RED,
            overlay_color=MTS_RED_DARK,
            color=MTS_WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(horizontal=24, vertical=10),
        ),
        on_click=open_details,
    )
    extra_button = ft.OutlinedButton(
        EXTRA_BUTTON_TEXT,
        style=ft.ButtonStyle(
            color=MTS_GRAY,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(horizontal=24, vertical=10),
        ),
        disabled=True,
    )
    header_icon_box, service_card = _catalog_card(
        icon=SERVICE_ICON,
        title=SERVICE_NAME,
        tagline=SERVICE_TAGLINE,
        action=more_button,
        header_bg=MTS_RED,
    )
    extra_icon_box, extra_card = _catalog_card(
        icon=EXTRA_SERVICE_ICON,
        title=EXTRA_SERVICE_NAME,
        tagline=EXTRA_SERVICE_TAGLINE,
        action=extra_button,
        header_bg="#5C5C5E",
    )
    open_button = ft.FilledButton(
        OPEN_BUTTON_TEXT,
        style=ft.ButtonStyle(
            bgcolor=MTS_RED,
            overlay_color=MTS_RED_DARK,
            color=MTS_WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(horizontal=24, vertical=10),
        ),
        on_click=lambda e: open_connected(),
    )
    connected_icon_box, connected_card = _catalog_card(
        icon=SERVICE_ICON,
        title=SERVICE_NAME,
        tagline="Подключена · настройки и Telegram",
        action=open_button,
        header_bg=MTS_RED,
    )
    connected_card.visible = False
    connected_empty = ft.Text(
        EMPTY_CONNECTED,
        size=13,
        color=MTS_GRAY,
    )
    connected_row = ft.Row(
        [connected_card],
        wrap=True,
        spacing=16,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
    available_row = ft.Row(
        [service_card, extra_card],
        wrap=True,
        spacing=16,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
    catalog = ft.Container(
        visible=False,
        padding=ft.Padding.symmetric(horizontal=24, vertical=20),
        content=ft.Column(
            [
                ft.Text(
                    CATALOG_TITLE,
                    size=22,
                    weight=ft.FontWeight.BOLD,
                    color=MTS_DARK,
                ),
                ft.Text(
                    CONNECTED_SECTION_TITLE,
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=MTS_DARK,
                ),
                connected_empty,
                connected_row,
                ft.Container(height=8),
                ft.Text(
                    AVAILABLE_TITLE,
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=MTS_DARK,
                ),
                available_row,
            ],
            spacing=12,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
    )

    login_btn = ft.FilledButton(
        LOGIN_BUTTON_TEXT,
        style=ft.ButtonStyle(
            bgcolor=MTS_RED,
            overlay_color=MTS_RED_DARK,
            color=MTS_WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(horizontal=24, vertical=12),
        ),
        on_click=lambda e: enter_app(),
    )
    login_gate = ft.Container(
        width=360,
        bgcolor=MTS_WHITE,
        border_radius=24,
        padding=ft.Padding.all(24),
        border=ft.Border.all(1, "#E8E8EA"),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=18,
            color="#1D1D1B22",
            offset=ft.Offset(0, 6),
        ),
        content=ft.Column(
            [
                ft.Text("МТС", size=22, weight=ft.FontWeight.BOLD, color=MTS_RED),
                ft.Text(LOGIN_TITLE, size=18, weight=ft.FontWeight.W_600, color=MTS_DARK),
                ft.Text(LOGIN_HINT, size=13, color=MTS_GRAY),
                login_phone,
                login_error,
                login_btn,
            ],
            spacing=12,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    login_wrap = ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=40),
        content=ft.Row(
            [login_gate],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )

    # --- Функции услуги (видны после подключения) ------------------------
    def _setting_check(title: str, desc: str, *, value: bool = True) -> tuple:
        """Строка настройки: квадратный чекбокс + подпись."""
        box = _square_checkbox(value=value)
        row = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            bgcolor=MTS_WHITE,
            border_radius=16,
            border=ft.Border.all(1, "#E8E8EA"),
            content=ft.Row(
                [
                    box,
                    ft.Column(
                        [
                            ft.Text(
                                title,
                                size=15,
                                weight=ft.FontWeight.W_600,
                                color=MTS_DARK,
                            ),
                            ft.Text(desc, size=13, color=MTS_GRAY),
                        ],
                        spacing=2,
                        tight=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        )
        return box, row

    setting_checks = []
    setting_rows = []
    for title, desc in FEATURES:
        box, row = _setting_check(title, desc)
        setting_checks.append(box)
        setting_rows.append(row)

    voice_check, voice_row = _setting_check(
        ROUTING_VOICE_LABEL,
        "ИИ отвечает голосом на входящий звонок",
        value=True,
    )
    chat_check, chat_row = _setting_check(
        ROUTING_CHAT_LABEL,
        "Переводить разговор в чат вместо голоса",
        value=False,
    )

    def _on_voice(e):
        if voice_check.value:
            chat_check.value = False
        elif not chat_check.value:
            voice_check.value = True
        page.update()

    def _on_chat(e):
        if chat_check.value:
            voice_check.value = False
        elif not voice_check.value:
            chat_check.value = True
        page.update()

    voice_check.on_change = _on_voice
    chat_check.on_change = _on_chat

    def _mark_tg_active(phone: str) -> None:
        tg_on["value"] = True
        tg_active.value = True
        tg_status_text.value = f"Активировано · {format_phone(phone)}"
        tg_status_text.color = MTS_RED
        page.update()

    def _on_tg_switch(e):
        e.control.value = tg_on["value"]
        page.update()

    tg_active = ft.Switch(
        value=False,
        active_color=MTS_RED,
        on_change=_on_tg_switch,
    )
    tg_status_text = ft.Text(
        "После /start в боте здесь загорится «Активировано»",
        size=13,
        color=MTS_GRAY,
    )

    def _poll_once() -> bool:
        phone = connected_phone["value"]
        if not phone:
            return False
        try:
            resp = httpx.get(
                f"{API_BASE}/api/v1/telegram/status",
                params={"phone": phone},
                timeout=2.0,
            )
        except httpx.RequestError:
            return False
        if resp.status_code == 200 and resp.json().get("activated"):
            _mark_tg_active(phone)
            return True
        return False

    def _start_poll():
        if tg_on.get("polling"):
            return
        tg_on["polling"] = True

        def loop():
            try:
                for _ in range(150):
                    if tg_on.get("stop"):
                        return
                    if _poll_once():
                        return
                    time.sleep(1.5)
            finally:
                tg_on["polling"] = False

        if hasattr(page, "run_thread"):
            page.run_thread(loop)
        else:
            threading.Thread(target=loop, daemon=True).start()

    tg_open_btn = ft.FilledButton(
        TELEGRAM_OPEN_TEXT,
        icon=ft.Icons.TELEGRAM,
        style=ft.ButtonStyle(
            bgcolor=MTS_RED,
            overlay_color=MTS_RED_DARK,
            color=MTS_WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
        ),
        on_click=lambda e: open_telegram(),
    )

    disconnect_btn = ft.TextButton(
        DISCONNECT_BUTTON_TEXT,
        style=ft.ButtonStyle(color=MTS_RED),
        on_click=lambda e: disconnect_service(),
    )

    features_panel = ft.Container(
        visible=False,
        bgcolor=MTS_BG,
        padding=ft.Padding.symmetric(horizontal=24, vertical=16),
        content=ft.Column(
            [
                ft.Text(
                    FEATURES_TITLE,
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    color=MTS_DARK,
                ),
                ft.Text(
                    ROUTING_TITLE,
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=MTS_DARK,
                ),
                voice_row,
                chat_row,
                *setting_rows,
                ft.Divider(height=1, color="#E8E8EA"),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                    bgcolor=MTS_WHITE,
                    border_radius=16,
                    border=ft.Border.all(1, "#E8E8EA"),
                    content=ft.Column(
                        [
                            ft.Text(
                                "Telegram-бот",
                                size=15,
                                weight=ft.FontWeight.W_600,
                                color=MTS_DARK,
                            ),
                            ft.Row(
                                [
                                    tg_active,
                                    tg_status_text,
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(TELEGRAM_TOGGLE_HINT, size=13, color=MTS_GRAY),
                            tg_open_btn,
                        ],
                        spacing=8,
                        tight=True,
                    ),
                ),
                ft.Text(
                    "Все изменения вступают в силу сразу — без повторной настройки",
                    size=12,
                    color=MTS_GRAY,
                ),
                disconnect_btn,
            ],
            spacing=12,
            tight=True,
        ),
    )

    # --- Шапка страницы --------------------------------------------------
    back_btn = ft.IconButton(
        icon=ft.Icons.ARROW_BACK,
        icon_color=MTS_WHITE,
        tooltip="К услугам",
        visible=False,
        on_click=lambda e: go_catalog(),
    )
    header_title = ft.Text(
        "МТС",
        size=22,
        weight=ft.FontWeight.BOLD,
        color=MTS_WHITE,
    )
    header_subtitle = ft.Text(
        f"| {LOGIN_TITLE}",
        size=15,
        color=MTS_WHITE,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
        expand=True,
    )
    profile_label = ft.Text(PROFILE_LABEL, size=10, color=MTS_WHITE)
    profile_phone = ft.Text("—", size=13, color=MTS_WHITE, weight=ft.FontWeight.W_600)
    profile_chip = ft.Container(
        visible=False,
        bgcolor=MTS_RED_DARK,
        border_radius=20,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        content=ft.Row(
            [
                ft.Icon(ft.Icons.PERSON, color=MTS_WHITE, size=20),
                ft.Column(
                    [
                        profile_label,
                        profile_phone,
                    ],
                    spacing=0,
                    tight=True,
                ),
            ],
            spacing=8,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    header = ft.Container(
        bgcolor=MTS_RED,
        padding=ft.Padding.symmetric(horizontal=32, vertical=12),
        content=ft.Row(
            [
                back_btn,
                header_title,
                header_subtitle,
                profile_chip,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    stage = ft.Column(
        [
            login_wrap,
            catalog,
            features_panel,
        ],
        tight=True,
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        spacing=0,
    )

    root = ft.Column(
        [
            header,
            stage,
        ],
        tight=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    page.add(root)

    # --- Адаптивность под размер экрана ----------------------------------
    def apply_responsive(width=None, height=None):
        """Пересчитывает размеры под текущий экран (мобильные/десктоп)."""
        width = width or getattr(page, "width", None) or 1100
        height = height or getattr(page, "height", None) or 720
        mobile = width <= MOBILE_BREAKPOINT

        h_pad = 16 if mobile else 32
        card_w = max(200, int(width) - 2 * h_pad) if mobile else CARD_SIZE
        service_card.width = card_w
        extra_card.width = card_w
        connected_card.width = card_w
        header_icon_box.height = 72 if mobile else 88
        extra_icon_box.height = 72 if mobile else 88
        connected_icon_box.height = 72 if mobile else 88
        catalog.padding = ft.Padding.symmetric(horizontal=h_pad, vertical=16 if mobile else 20)
        available_row.alignment = ft.MainAxisAlignment.CENTER
        connected_row.alignment = ft.MainAxisAlignment.CENTER

        header.padding = ft.Padding.symmetric(
            horizontal=h_pad, vertical=12 if mobile else 16
        )
        header_title.size = 18 if mobile else 22
        header_subtitle.size = 13 if mobile else 15
        profile_label.visible = not mobile
        profile_phone.size = 12 if mobile else 13

        more_button.style.padding = ft.Padding.symmetric(
            horizontal=32 if mobile else 24,
            vertical=14 if mobile else 10,
        )
        more_button.style.shape = ft.RoundedRectangleBorder(
            radius=14 if mobile else 12
        )

        dialog_box.width = min(420, max(240, width - 48))
        dialog_box.height = min(420, height - 200) if mobile else None

        login_gate.width = min(360, max(260, width - 2 * h_pad))
        features_panel.padding = ft.Padding.symmetric(horizontal=h_pad, vertical=16)

        page.update()

    page.ui = {
        "service_card": service_card,
        "extra_card": extra_card,
        "connected_card": connected_card,
        "connected_empty": connected_empty,
        "open_btn": open_button,
        "profile": profile_chip,
        "profile_phone": profile_phone,
        "catalog": catalog,
        "features_panel": features_panel,
        "connect_btn": connect_btn,
        "disconnect_btn": disconnect_btn,
        "more_btn": more_button,
        "consent": consent_checkbox,
        "consent_error": consent_error,
        "tg_open_btn": tg_open_btn,
        "tg_active": tg_active,
        "tg_status_text": tg_status_text,
        "phone_field": login_phone,
        "login_gate": login_gate,
        "login_btn": login_btn,
        "login_error": login_error,
        "setting_checks": setting_checks,
        "header_subtitle": header_subtitle,
        "back_btn": back_btn,
        "stage": stage,
        "dialog": details_dialog,
        "dialog_box": dialog_box,
    }

    page.on_resize = lambda e: apply_responsive(e.width, e.height)
    apply_responsive()


if __name__ == "__main__":
    ft.run(main)
