"""Страница подключения услуги «ИИ-агент для звонков».

Flet 0.86 · стиль МТС · адаптив под десктоп, планшеты и мобильные экраны.

Запуск:  python -m frontend.app
"""

import os
import threading
import time

import flet as ft
import httpx

from .phone_utils import format_phone, normalize_phone
from .labels import ACTION_RU, INTENT_RU, PRIORITY_RU
from .live_call_flet import LiveCallController
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
    TRY_SERVICE_TEXT,
    TRY_SERVICE_HINT,
    FEATURES_TITLE,
    FEATURES,
    ROUTING_TITLE,
    ROUTING_LABELS,
    ROUTING_VOICE,
    ROUTING_CHAT,
    ROUTING_HYBRID,
    TEMPLATES_TAB_TITLE,
    TEMPLATES_HINT,
    TEMPLATES_USE_LABEL,
    TEMPLATE_ADD_TITLE,
    TEMPLATE_NAME_LABEL,
    TEMPLATE_TEXT_LABEL,
    TEMPLATE_KIND_LABEL,
    TEMPLATE_KIND_LABELS,
    TEMPLATE_ADD_BUTTON,
    TEMPLATE_DELETE,
    TEMPLATE_EMPTY,
    RULES_SECTION_TITLE,
    RULES_HINT,
    ROUTING_HINT,
    ESCALATION_STUB,
    EDIT_SAVE_TEXT,
    EDIT_SAVED_TEXT,
    EDIT_HINT,
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
# Локально всегда :8000. Tunnel (DEMO_WEB_URL) — только для QR/телефона, не для Flet на ПК:
# иначе мёртвый cloudflare URL даёт «API недоступен» при живом uvicorn.
# APK/телефон: задайте API_BASE или DEMO_API_URL явно.
API_BASE = (
    os.getenv("API_BASE")
    or os.getenv("DEMO_API_URL")
    or "http://127.0.0.1:8000"
).rstrip("/")
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


def _mts_text_field(**kwargs) -> ft.TextField:
    """Поле ввода: тёмный текст значения, серая подсказка/лейбл — не сливаются."""
    defaults = dict(
        color=MTS_DARK,
        cursor_color=MTS_RED,
        bgcolor=MTS_WHITE,
        filled=True,
        fill_color=MTS_WHITE,
        border_color=MTS_GRAY,
        focused_border_color=MTS_RED,
        focused_color=MTS_DARK,
        label_style=ft.TextStyle(color=MTS_GRAY, size=13),
        hint_style=ft.TextStyle(color=MTS_GRAY, size=14),
        text_style=ft.TextStyle(color=MTS_DARK, size=15),
    )
    defaults.update(kwargs)
    return ft.TextField(**defaults)


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
    bind_token = {"value": ""}
    live_call_ref: dict = {"ctl": None}
    service_on = {"value": False}
    tg_on = {"value": False}
    login_phone = _mts_text_field(
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
        bind_token["value"] = _register_line(phone)
        profile_phone.value = format_phone(phone)
        profile_chip.visible = True
        # Восстановить подключение услуги с бэка (тот же номер — услуга уже есть).
        restored = _restore_service_state(phone)
        _show_catalog()
        if restored:
            _start_poll()

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
        bind_token["value"] = _register_line(phone)
        close_dialog()
        service_on["value"] = True
        _open_settings(reset_tg=not tg_on["value"], connected=True)
        _start_poll()

    def open_connected(_=None):
        """Уже подключена — сразу в настройки, без повторного «Подключить»."""
        _open_settings(reset_tg=False, connected=True)

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

    def _open_settings(*, reset_tg: bool, connected: bool = True):
        phone = connected_phone["value"]
        header_subtitle.value = f"| {SERVICE_NAME}"
        page.title = f"МТС — {SERVICE_NAME}"
        login_gate.visible = False
        login_wrap.visible = False
        catalog.visible = False
        features_panel.visible = True
        back_btn.visible = True
        _load_settings()
        _sync_tg_open_url()
        if reset_tg:
            tg_on["value"] = False
            tg_on["stop"] = False
            tg_active.value = False
            tg_status_text.value = f"Ожидает /start · {format_phone(phone)}"
            tg_status_text.color = MTS_GRAY
        _push_settings(connected=connected)
        _show_tab("dash")

    def go_catalog(_=None):
        """Стрелка назад: услуга остаётся подключённой."""
        _show_catalog()

    def disconnect_service(_=None):
        """Снять услугу: вернуть карточку в «Доступные»."""
        _stop_tg_poll()
        tg_on["value"] = False
        tg_active.value = False
        tg_status_text.value = "После /start в боте здесь загорится «Активировано»"
        tg_status_text.color = MTS_GRAY
        service_on["value"] = False
        phone = connected_phone["value"]
        _push_settings(connected=False)
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

    def _register_line(phone: str) -> str:
        """Регистрация линии + одноразовый токен (не светим сырой номер в deep link)."""
        try:
            resp = httpx.post(
                f"{API_BASE}/api/v1/telegram/register",
                json={"phone": phone},
                timeout=3.0,
            )
            if resp.status_code == 200:
                return str((resp.json() or {}).get("bind_token") or "")
        except httpx.RequestError:
            pass
        return ""

    def _bot_start_url(phone: str = "", token: str = "") -> str:
        base = TELEGRAM_BOT_URL.rstrip("/")
        token = (token or bind_token["value"] or "").strip()
        if token.startswith("b"):
            return f"{base}?start={token}"
        # Без токена — голый бот (пользователь введёт свой номер), не чужой pending.
        return base

    def _open_live_call(_=None):
        ctl = live_call_ref.get("ctl")
        if ctl is not None:
            ctl.refresh_line(reload=True)
        _show_tab("call")

    def _sync_tg_open_url():
        """Ссылка на кнопке = клиентский <a href> с одноразовым токеном этой сессии."""
        phone = connected_phone["value"]
        if phone and not bind_token["value"]:
            bind_token["value"] = _register_line(phone)
        tg_open_btn.url = _bot_start_url(phone, bind_token["value"])

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

    history_check = setting_checks[0]
    notify_critical_check = setting_checks[1]
    strict_mode_check = setting_checks[2]

    routing_dropdown = ft.Dropdown(
        label=ROUTING_TITLE,
        value=ROUTING_VOICE,
        options=[
            ft.dropdown.Option(key=key, text=label)
            for key, label in ROUTING_LABELS.items()
        ],
        width=min(320, 280),
        color=MTS_DARK,
        bgcolor=MTS_WHITE,
        filled=True,
        fill_color=MTS_WHITE,
        border_color=MTS_GRAY,
        focused_border_color=MTS_RED,
        label_style=ft.TextStyle(color=MTS_GRAY, size=13),
        text_style=ft.TextStyle(color=MTS_DARK, size=15),
    )

    scenarios_switch = _square_checkbox(label=TEMPLATES_USE_LABEL, value=True)
    scenarios_cache: list[dict] = []
    scenarios_list = ft.Column(spacing=8, tight=True)
    scenarios_status = ft.Text("", size=12, color=MTS_GRAY)
    templates_off_hint = ft.Text(
        "Шаблоны выключены — список скрыт, агент их не использует.",
        size=12,
        color=MTS_GRAY,
        visible=False,
    )
    new_scenario_name = _mts_text_field(label=TEMPLATE_NAME_LABEL)
    new_scenario_text = _mts_text_field(
        label=TEMPLATE_TEXT_LABEL,
        multiline=True,
        min_lines=2,
        max_lines=4,
    )
    new_scenario_kind = ft.Dropdown(
        label=TEMPLATE_KIND_LABEL,
        value="custom",
        options=[
            ft.dropdown.Option(key=k, text=v) for k, v in TEMPLATE_KIND_LABELS.items()
        ],
        bgcolor=MTS_WHITE,
        filled=True,
        fill_color=MTS_WHITE,
        color=MTS_DARK,
        border_color=MTS_GRAY,
        focused_border_color=MTS_RED,
        label_style=ft.TextStyle(color=MTS_GRAY, size=13),
        text_style=ft.TextStyle(color=MTS_DARK, size=15),
    )

    def _templates_from_cache() -> tuple[str, str]:
        greeting = ""
        faq_parts: list[str] = []
        for item in scenarios_cache:
            if not item.get("enabled", True):
                continue
            kind = str(item.get("kind") or "custom")
            text = str(item.get("text") or "").strip()
            name = str(item.get("name") or "").strip()
            if not text:
                continue
            if kind == "greeting" and not greeting:
                greeting = text
            elif kind == "faq":
                faq_parts.append(f"{name}: {text}" if name else text)
            elif kind == "custom":
                faq_parts.append(f"{name}: {text}" if name else text)
        return greeting, "\n".join(faq_parts)

    def _settings_payload(*, connected: bool | None = None) -> dict:
        routing = routing_dropdown.value or ROUTING_VOICE
        if routing not in ROUTING_LABELS:
            routing = ROUTING_VOICE
        greeting, faq = _templates_from_cache()
        payload = {
            "phone": connected_phone["value"],
            "connected": bool(service_on["value"]) if connected is None else bool(connected),
            "routing": routing,
            "history": bool(history_check.value),
            "scenarios": bool(scenarios_switch.value),
            "hotline": True,
            "notify": "critical" if notify_critical_check.value else "all",
            "mode": "strict" if strict_mode_check.value else "loyal",
            "template_greeting": greeting,
            "template_faq": faq,
        }
        return payload

    def _push_settings(_=None, *, connected: bool | None = None):
        """Фронт — источник правды; бот только читает (даже без /start)."""
        phone = connected_phone["value"]
        if len(phone) < 10:
            return
        try:
            httpx.post(
                f"{API_BASE}/api/v1/service/settings",
                json=_settings_payload(connected=connected),
                timeout=3.0,
            )
        except httpx.RequestError:
            pass

    def _apply_settings(data: dict) -> None:
        routing = data.get("routing") or ROUTING_VOICE
        if routing not in ROUTING_LABELS:
            routing = ROUTING_VOICE
        routing_dropdown.value = routing
        history_check.value = bool(data.get("history", True))
        scenarios_switch.value = bool(data.get("scenarios", True))
        notify_critical_check.value = data.get("notify") == "critical"
        strict_mode_check.value = data.get("mode", "strict") != "loyal"

    def _restore_service_state(phone: str) -> bool:
        """Подтянуть connected/настройки с API; True если услуга уже подключена."""
        if len(phone) < 10:
            service_on["value"] = False
            return False
        try:
            resp = httpx.get(
                f"{API_BASE}/api/v1/service/settings",
                params={"phone": phone},
                timeout=3.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                _apply_settings(data)
                on = bool(data.get("connected"))
                service_on["value"] = on
                if on:
                    # Восстановить статус Telegram без сброса
                    try:
                        st = httpx.get(
                            f"{API_BASE}/api/v1/telegram/status",
                            params={"phone": phone},
                            timeout=2.0,
                        )
                        if st.status_code == 200 and st.json().get("activated"):
                            tg_on["value"] = True
                            tg_active.value = True
                            tg_status_text.value = f"Активировано · {format_phone(phone)}"
                            tg_status_text.color = MTS_RED
                        else:
                            tg_on["value"] = False
                            tg_active.value = False
                            tg_status_text.value = f"Ожидает /start · {format_phone(phone)}"
                            tg_status_text.color = MTS_GRAY
                    except httpx.RequestError:
                        pass
                return on
        except httpx.RequestError:
            pass
        service_on["value"] = False
        return False

    def _load_settings() -> None:
        """Подтянуть routing/шаблоны; флаг connected трогает только restore/connect/disconnect."""
        phone = connected_phone["value"]
        if len(phone) < 10:
            return
        try:
            resp = httpx.get(
                f"{API_BASE}/api/v1/service/settings",
                params={"phone": phone},
                timeout=3.0,
            )
            if resp.status_code == 200:
                _apply_settings(resp.json())
                _apply_effects()
        except httpx.RequestError:
            pass

    hist_filter = {"critical": False}
    ui_tab = {"name": "dash"}

    effect_banner_text = ft.Text("", size=12, color=MTS_DARK)
    effect_banner = ft.Container(
        visible=True,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        bgcolor="#FFF5F5",
        border_radius=12,
        border=ft.Border.all(1, "#F5C6C8"),
        content=effect_banner_text,
    )
    history_off_hint = ft.Text(
        "История выключена — раздел недоступен, пока не включите галочку.",
        size=12,
        color=MTS_RED,
        visible=False,
    )
    tg_status_hint = ft.Text(
        "Пуши в Telegram: все звонки (если бот подключён)",
        size=12,
        color=MTS_GRAY,
    )
    dash_body = ft.Column(spacing=8, tight=True)
    history_list = ft.Column(spacing=8, tight=True)
    selected_call = {"id": None}
    detail_meta = ft.Text("", size=13, color=MTS_DARK, selectable=True)
    escalation_banner = ft.Text(
        ESCALATION_STUB,
        size=12,
        color=MTS_RED,
        visible=False,
    )
    edit_input = _mts_text_field(label="Вход (речь звонящего)", multiline=True, min_lines=2, max_lines=4)
    edit_output = _mts_text_field(label="Выход (ответ агента)", multiline=True, min_lines=2, max_lines=4)
    edit_summary = _mts_text_field(label="Резюме для Ивана", multiline=True, min_lines=2, max_lines=3)
    edit_status = ft.Text("", size=12, color=MTS_GRAY)
    rules_list = ft.Column(spacing=8, tight=True)
    rules_status = ft.Text("", size=12, color=MTS_GRAY)

    def _save_call_edit(_=None):
        cid = selected_call.get("id")
        phone = connected_phone["value"]
        if not cid or len(phone) < 10:
            return
        try:
            resp = httpx.patch(
                f"{API_BASE}/api/v1/calls/{cid}",
                params={"phone": phone},
                json={
                    "user_message": (edit_input.value or "").strip(),
                    "agent_response": (edit_output.value or "").strip(),
                    "summary": (edit_summary.value or "").strip(),
                },
                timeout=5.0,
            )
        except httpx.RequestError:
            edit_status.value = "API недоступен"
            edit_status.color = MTS_RED
            page.update()
            return
        if resp.status_code == 200:
            edit_status.value = EDIT_SAVED_TEXT
            edit_status.color = MTS_DARK
            _load_history(critical=hist_filter["critical"])
        else:
            edit_status.value = f"Ошибка сохранения ({resp.status_code})"
            edit_status.color = MTS_RED
        page.update()

    save_edit_btn = ft.FilledButton(
        EDIT_SAVE_TEXT,
        style=ft.ButtonStyle(bgcolor=MTS_RED, color=MTS_WHITE),
        on_click=_save_call_edit,
    )
    detail_box = ft.Container(
        visible=False,
        padding=ft.Padding.all(14),
        bgcolor=MTS_WHITE,
        border_radius=16,
        border=ft.Border.all(1, "#E8E8EA"),
        content=ft.Column(
            [
                detail_meta,
                escalation_banner,
                ft.Text(EDIT_HINT, size=12, color=MTS_GRAY),
                edit_input,
                edit_output,
                edit_summary,
                ft.Row([save_edit_btn, edit_status], spacing=10),
            ],
            spacing=8,
            tight=True,
        ),
    )

    def _sync_template_fields():
        enabled = bool(scenarios_switch.value)
        scenarios_list.visible = enabled
        add_scenario_box.visible = enabled
        scenarios_status.visible = enabled
        templates_off_hint.visible = not enabled

    def _effect_summary() -> str:
        routing = ROUTING_LABELS.get(routing_dropdown.value or ROUTING_VOICE, "Голос")
        bits = [
            f"Ответ: {routing.lower()}",
            f"История: {'вкл' if history_check.value else 'выкл'}",
            f"Шаблоны: {'вкл' if scenarios_switch.value else 'выкл'}",
            f"Режим: {'строгий' if strict_mode_check.value else 'лояльный'}",
        ]
        if notify_critical_check.value:
            bits.append("TG-пуши: только важные")
        else:
            bits.append("TG-пуши: все (если бот есть)")
        return " · ".join(bits)

    def _apply_effects():
        effect_banner_text.value = _effect_summary()
        history_off_hint.visible = not history_check.value
        hist_all_btn.disabled = not history_check.value
        hist_crit_btn.disabled = not history_check.value
        refresh_hist_btn.disabled = not history_check.value
        if not history_check.value:
            history_list.controls = [
                ft.Text(
                    "История выключена в настройках — включите «История звонков и саммари».",
                    size=13,
                    color=MTS_GRAY,
                )
            ]
            detail_box.visible = False
        tg_status_hint.value = (
            "Пуши в Telegram: только важные"
            if notify_critical_check.value
            else "Пуши в Telegram: все звонки (если бот подключён)"
        )

    def _fmt_when(raw) -> str:
        return str(raw or "—").replace("T", " ")[:16]

    def _dash_metric(title: str, value: str, subtitle: str, *, accent: bool = False) -> ft.Container:
        return ft.Container(
            expand=True,
            padding=ft.Padding.all(14),
            bgcolor=MTS_WHITE,
            border_radius=16,
            border=ft.Border.all(1, MTS_RED if accent else "#E8E8EA"),
            content=ft.Column(
                [
                    ft.Text(title, size=12, color=MTS_GRAY),
                    ft.Text(
                        value,
                        size=26,
                        weight=ft.FontWeight.BOLD,
                        color=MTS_RED if accent else MTS_DARK,
                    ),
                    ft.Text(subtitle, size=12, color=MTS_GRAY),
                ],
                spacing=4,
                tight=True,
            ),
        )

    def _dash_bar_row(label: str, count: int, total: int) -> ft.Control:
        share = (count / total) if total else 0
        width_frac = max(0.06, min(1.0, share))
        filled = max(1, int(round(width_frac * 100)))
        empty = max(1, 100 - filled)
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(label, size=13, color=MTS_DARK, expand=True),
                        ft.Text(str(count), size=13, weight=ft.FontWeight.W_600, color=MTS_DARK),
                    ],
                    spacing=8,
                ),
                ft.Container(
                    height=8,
                    bgcolor="#EFEFF1",
                    border_radius=8,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    content=ft.Row(
                        [
                            ft.Container(
                                height=8,
                                bgcolor=MTS_RED,
                                border_radius=8,
                                expand=filled,
                            ),
                            ft.Container(expand=empty),
                        ],
                        spacing=0,
                    ),
                ),
            ],
            spacing=4,
            tight=True,
        )

    def _dash_chip(label: str, count: int) -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor="#F7F7F8",
            border_radius=20,
            border=ft.Border.all(1, "#E8E8EA"),
            content=ft.Text(f"{label}  {count}", size=12, color=MTS_DARK),
        )

    def _load_dashboard():
        dash_body.controls.clear()
        try:
            phone = connected_phone["value"]
            resp = httpx.get(
                f"{API_BASE}/api/v1/calls/stats",
                params={"phone": phone},
                timeout=5.0,
            )
        except httpx.RequestError:
            dash_body.controls.append(
                ft.Container(
                    padding=ft.Padding.all(16),
                    bgcolor="#FFF5F5",
                    border_radius=14,
                    border=ft.Border.all(1, "#F5C6C8"),
                    content=ft.Text(
                        "API недоступен — запустите uvicorn на :8000",
                        color=MTS_RED,
                        size=13,
                    ),
                )
            )
            return
        if resp.status_code != 200:
            dash_body.controls.append(ft.Text("Дашборд недоступен", color=MTS_RED, size=13))
            return
        s = resp.json()
        total = int(s.get("total") or 0)
        critical = int(s.get("critical") or 0)
        routine = int(s.get("routine") or max(0, total - critical))
        share_raw = float(s.get("critical_share") or 0)
        # API отдаёт долю 0..1 или уже проценты
        share_pct = int(round(share_raw * 100)) if share_raw <= 1 else int(round(share_raw))

        dash_body.controls.append(
            ft.Row(
                [
                    _dash_metric("Всего", str(total), "карточек линии"),
                    _dash_metric("Важные", str(critical), f"{share_pct}% от всех", accent=True),
                    _dash_metric("Рутина", str(routine), "без эскалации"),
                ],
                spacing=10,
            )
        )

        if not total:
            dash_body.controls.append(
                ft.Container(
                    margin=ft.Margin.only(top=8),
                    padding=ft.Padding.all(20),
                    bgcolor=MTS_WHITE,
                    border_radius=16,
                    border=ft.Border.all(1, "#E8E8EA"),
                    content=ft.Column(
                        [
                            ft.Text("Пока тихо", size=16, weight=ft.FontWeight.W_600, color=MTS_DARK),
                            ft.Text(
                                "После демо-звонка в Telegram здесь появятся счётчики "
                                "и разбивка по намерениям.",
                                size=13,
                                color=MTS_GRAY,
                            ),
                        ],
                        spacing=6,
                        tight=True,
                    ),
                )
            )
            return

        intents = s.get("by_intent") or {}
        if intents:
            dash_body.controls.append(
                ft.Container(
                    margin=ft.Margin.only(top=4),
                    padding=ft.Padding.all(14),
                    bgcolor=MTS_WHITE,
                    border_radius=16,
                    border=ft.Border.all(1, "#E8E8EA"),
                    content=ft.Column(
                        [
                            ft.Text("Намерения", size=14, weight=ft.FontWeight.W_600, color=MTS_DARK),
                            ft.Text("Кто звонил и зачем — по классификации агента", size=12, color=MTS_GRAY),
                            *[_dash_bar_row(INTENT_RU.get(str(k), str(k)), int(v), total) for k, v in intents.items()],
                        ],
                        spacing=10,
                        tight=True,
                    ),
                )
            )

        actions = s.get("by_action") or {}
        if actions:
            chips = [
                _dash_chip(ACTION_RU.get(str(k), str(k)), int(v))
                for k, v in actions.items()
            ]
            dash_body.controls.append(
                ft.Container(
                    padding=ft.Padding.all(14),
                    bgcolor=MTS_WHITE,
                    border_radius=16,
                    border=ft.Border.all(1, "#E8E8EA"),
                    content=ft.Column(
                        [
                            ft.Text("Что делать дальше", size=14, weight=ft.FontWeight.W_600, color=MTS_DARK),
                            ft.Text("Действия, которые агент рекомендует Ивану", size=12, color=MTS_GRAY),
                            ft.Row(chips, spacing=8, wrap=True),
                        ],
                        spacing=10,
                        tight=True,
                    ),
                )
            )

    def _show_call_detail(item: dict):
        flag = "⚠️ Важно" if item.get("is_critical") else "Звонок"
        action_key = str(item.get("action_required") or "")
        action = ACTION_RU.get(action_key, action_key or "—")
        intent = INTENT_RU.get(str(item.get("intent") or ""), str(item.get("intent") or "—"))
        direction = "входящий" if (item.get("direction") or "inbound") == "inbound" else "исходящий"
        inbound = item.get("input") or item.get("user_message") or ""
        outbound = item.get("output") or item.get("agent_response") or ""
        selected_call["id"] = item.get("id")
        lines = [
            f"{flag} #{item.get('id')}",
            f"Когда: {_fmt_when(item.get('created_at'))}",
            f"Линия: {format_phone(str(item.get('line_phone') or connected_phone['value']))}",
            f"Направление: {direction}",
            f"Звонящий: {format_phone(str(item.get('caller_phone') or ''))}",
            f"Кто: {item.get('caller_name') or 'не представился'}",
            f"Намерение: {intent}",
            f"Приоритет: {PRIORITY_RU.get(str(item.get('priority') or ''), '—')}",
            f"Действие: {action}",
        ]
        step = str(item.get("recommended_next_step") or "").strip()
        if step:
            lines += [f"Дальше: {step}"]
        detail_meta.value = "\n".join(lines)
        escalation_banner.visible = action_key == "transfer_to_human"
        edit_input.value = str(inbound)
        edit_output.value = str(outbound)
        edit_summary.value = str(item.get("summary") or "")
        edit_status.value = ""
        detail_box.visible = True

    def _call_card(item: dict) -> ft.Container:
        flag = "⚠️" if item.get("is_critical") else "•"
        title = (
            f"{flag} #{item.get('id')}  "
            f"{format_phone(str(item.get('caller_phone') or ''))}"
        )
        meta = (
            f"{_fmt_when(item.get('created_at'))} · "
            f"{INTENT_RU.get(str(item.get('intent') or ''), str(item.get('intent') or '—'))}"
        )
        return ft.Container(
            padding=ft.Padding.all(12),
            bgcolor=MTS_WHITE,
            border_radius=14,
            border=ft.Border.all(1, "#E8E8EA"),
            on_click=lambda e, it=item: (_show_call_detail(it), page.update()),
            content=ft.Column(
                [
                    ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=MTS_DARK),
                    ft.Text(meta, size=12, color=MTS_GRAY),
                    ft.Text(str(item.get("summary") or "—")[:180], size=13, color=MTS_DARK),
                ],
                spacing=4,
                tight=True,
            ),
        )

    def _load_history(*, critical: bool):
        hist_filter["critical"] = critical
        history_list.controls.clear()
        detail_box.visible = False
        if not history_check.value:
            _apply_effects()
            return
        try:
            resp = httpx.get(
                f"{API_BASE}/api/v1/calls",
                params={
                    "phone": connected_phone["value"],
                    "limit": 20,
                    "critical_only": critical,
                },
                timeout=5.0,
            )
        except httpx.RequestError:
            history_list.controls.append(
                ft.Text("API недоступен — запустите uvicorn на :8000", color=MTS_RED, size=13)
            )
            return
        if resp.status_code != 200:
            history_list.controls.append(ft.Text("История недоступна", color=MTS_RED, size=13))
            return
        payload = resp.json()
        items = payload.get("items") or []
        total = int(payload.get("total") or len(items))
        title = "Важные звонки" if critical else "Все звонки"
        history_list.controls.append(
            ft.Text(f"{title} · показано {len(items)} из {total}", size=13, color=MTS_GRAY)
        )
        if not items:
            history_list.controls.append(
                ft.Text(
                    "Важных обращений пока нет." if critical else "История пуста.",
                    size=13,
                    color=MTS_GRAY,
                )
            )
            return
        for item in items:
            history_list.controls.append(_call_card(item))

    def _tab_style(active: bool) -> ft.ButtonStyle:
        return ft.ButtonStyle(
            bgcolor=MTS_RED if active else MTS_WHITE,
            color=MTS_WHITE if active else MTS_DARK,
        )

    def _toggle_rule(rule: dict, enabled: bool):
        body = {
            "id": rule.get("id"),
            "name": rule.get("name") or "rule",
            "description": rule.get("description") or "",
            "keywords": rule.get("keywords") or [],
            "is_critical": rule.get("is_critical"),
            "intent": rule.get("intent"),
            "action_required": rule.get("action_required"),
            "enabled": bool(enabled),
        }
        try:
            resp = httpx.put(
                f"{API_BASE}/api/v1/routing_rules",
                json=body,
                timeout=5.0,
            )
        except httpx.RequestError:
            rules_status.value = "API недоступен — правило не сохранено"
            rules_status.color = MTS_RED
            _load_rules()
            page.update()
            return
        if resp.status_code == 200:
            rules_status.value = f"«{body['name']}»: {'вкл' if enabled else 'выкл'}"
            rules_status.color = MTS_DARK
        else:
            rules_status.value = f"Ошибка ({resp.status_code})"
            rules_status.color = MTS_RED
            _load_rules()
        page.update()

    def _load_rules():
        rules_list.controls.clear()
        try:
            resp = httpx.get(f"{API_BASE}/api/v1/routing_rules", timeout=5.0)
        except httpx.RequestError:
            rules_list.controls.append(
                ft.Text("API недоступен — запустите uvicorn на :8000", color=MTS_RED, size=13)
            )
            return
        if resp.status_code != 200:
            rules_list.controls.append(ft.Text("Правила недоступны", color=MTS_RED, size=13))
            return
        items = resp.json().get("items") or []
        if not items:
            rules_list.controls.append(ft.Text("Список правил пуст.", size=13, color=MTS_GRAY))
            return
        for rule in items:
            box = _square_checkbox(
                value=bool(rule.get("enabled", True)),
                on_change=lambda e, r=rule: _toggle_rule(r, bool(e.control.value)),
            )
            action = ACTION_RU.get(str(rule.get("action_required") or ""), str(rule.get("action_required") or "—"))
            crit = "важно" if rule.get("is_critical") else "рутина"
            if rule.get("is_critical") is None:
                crit = "как модель"
            row = ft.Container(
                padding=ft.Padding.all(12),
                bgcolor=MTS_WHITE,
                border_radius=14,
                border=ft.Border.all(1, "#E8E8EA"),
                content=ft.Row(
                    [
                        box,
                        ft.Column(
                            [
                                ft.Text(
                                    str(rule.get("name") or "Правило"),
                                    size=14,
                                    weight=ft.FontWeight.W_600,
                                    color=MTS_DARK,
                                ),
                                ft.Text(
                                    str(rule.get("description") or ""),
                                    size=12,
                                    color=MTS_GRAY,
                                ),
                                ft.Text(
                                    f"Действие: {action} · {crit}",
                                    size=12,
                                    color=MTS_DARK,
                                ),
                            ],
                            spacing=2,
                            tight=True,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            )
            rules_list.controls.append(row)

    def _show_tab(name: str):
        ui_tab["name"] = name
        dash_section.visible = name == "dash"
        hist_section.visible = name == "hist"
        tpl_section.visible = name == "tpl"
        set_section.visible = name == "set"
        call_section.visible = name == "call"
        tab_dash.style = _tab_style(name == "dash")
        tab_hist.style = _tab_style(name == "hist")
        tab_tpl.style = _tab_style(name == "tpl")
        tab_set.style = _tab_style(name == "set")
        tab_call.style = _tab_style(name == "call")
        if name == "dash":
            _load_dashboard()
        elif name == "hist":
            _load_history(critical=hist_filter["critical"])
        elif name == "tpl":
            _load_scenarios()
        elif name == "set":
            _load_rules()
        elif name == "call":
            ctl = live_call_ref.get("ctl")
            if ctl is not None:
                ctl.refresh_line()
        _apply_effects()
        page.update()

    def _upsert_scenario(body: dict, *, reload: bool = True) -> bool:
        try:
            resp = httpx.put(
                f"{API_BASE}/api/v1/scenarios",
                json=body,
                timeout=5.0,
            )
        except httpx.RequestError:
            scenarios_status.value = "API недоступен — шаблон не сохранён"
            scenarios_status.color = MTS_RED
            page.update()
            return False
        if resp.status_code != 200:
            scenarios_status.value = f"Ошибка сохранения ({resp.status_code})"
            scenarios_status.color = MTS_RED
            page.update()
            return False
        scenarios_status.value = "Сохранено"
        scenarios_status.color = MTS_DARK
        if reload:
            _load_scenarios()
            _push_settings()
        page.update()
        return True

    def _toggle_scenario(item: dict, enabled: bool):
        body = {
            "id": item.get("id"),
            "name": item.get("name") or "Шаблон",
            "kind": item.get("kind") or "custom",
            "text": item.get("text") or "",
            "enabled": bool(enabled),
        }
        _upsert_scenario(body)

    def _save_scenario_fields(item: dict, name_field: ft.TextField, text_field: ft.TextField):
        body = {
            "id": item.get("id"),
            "name": (name_field.value or "").strip() or "Шаблон",
            "kind": item.get("kind") or "custom",
            "text": (text_field.value or "").strip(),
            "enabled": bool(item.get("enabled", True)),
        }
        _upsert_scenario(body)

    def _delete_scenario(item: dict):
        sid = item.get("id")
        if not sid:
            return
        try:
            resp = httpx.delete(f"{API_BASE}/api/v1/scenarios/{sid}", timeout=5.0)
        except httpx.RequestError:
            scenarios_status.value = "API недоступен — не удалено"
            scenarios_status.color = MTS_RED
            page.update()
            return
        if resp.status_code == 200:
            scenarios_status.value = "Удалено"
            scenarios_status.color = MTS_DARK
            _load_scenarios()
            _push_settings()
        else:
            scenarios_status.value = f"Ошибка удаления ({resp.status_code})"
            scenarios_status.color = MTS_RED
        page.update()

    def _scenario_card(item: dict) -> ft.Container:
        kind = str(item.get("kind") or "custom")
        kind_label = TEMPLATE_KIND_LABELS.get(kind, kind)
        name_field = _mts_text_field(
            label=TEMPLATE_NAME_LABEL,
            value=str(item.get("name") or ""),
        )
        text_field = _mts_text_field(
            label=TEMPLATE_TEXT_LABEL,
            value=str(item.get("text") or ""),
            multiline=True,
            min_lines=2,
            max_lines=4,
        )
        name_field.on_blur = lambda e, it=item, nf=name_field, tf=text_field: _save_scenario_fields(
            it, nf, tf
        )
        text_field.on_blur = lambda e, it=item, nf=name_field, tf=text_field: _save_scenario_fields(
            it, nf, tf
        )
        box = _square_checkbox(
            value=bool(item.get("enabled", True)),
            on_change=lambda e, it=item: _toggle_scenario(it, bool(e.control.value)),
        )
        delete_btn = ft.TextButton(
            TEMPLATE_DELETE,
            style=ft.ButtonStyle(color=MTS_RED),
            on_click=lambda e, it=item: _delete_scenario(it),
        )
        return ft.Container(
            padding=ft.Padding.all(12),
            bgcolor=MTS_WHITE,
            border_radius=14,
            border=ft.Border.all(1, "#E8E8EA"),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            box,
                            ft.Text(
                                kind_label,
                                size=12,
                                color=MTS_GRAY,
                                expand=True,
                            ),
                            delete_btn,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    name_field,
                    text_field,
                ],
                spacing=8,
                tight=True,
            ),
        )

    def _load_scenarios():
        scenarios_list.controls.clear()
        scenarios_cache.clear()
        try:
            resp = httpx.get(f"{API_BASE}/api/v1/scenarios", timeout=5.0)
        except httpx.RequestError:
            scenarios_list.controls.append(
                ft.Text("API недоступен — запустите uvicorn на :8000", color=MTS_RED, size=13)
            )
            return
        if resp.status_code != 200:
            scenarios_list.controls.append(ft.Text("Шаблоны недоступны", color=MTS_RED, size=13))
            return
        items = resp.json().get("items") or []
        scenarios_cache.extend(items)
        if not items:
            scenarios_list.controls.append(
                ft.Text(TEMPLATE_EMPTY, size=13, color=MTS_GRAY)
            )
            return
        for item in items:
            scenarios_list.controls.append(_scenario_card(item))

    def _add_scenario(_=None):
        name = (new_scenario_name.value or "").strip()
        text = (new_scenario_text.value or "").strip()
        if not name or not text:
            scenarios_status.value = "Укажите название и текст"
            scenarios_status.color = MTS_RED
            page.update()
            return
        ok = _upsert_scenario(
            {
                "name": name,
                "kind": new_scenario_kind.value or "custom",
                "text": text,
                "enabled": True,
            }
        )
        if ok:
            new_scenario_name.value = ""
            new_scenario_text.value = ""
            new_scenario_kind.value = "custom"
            page.update()

    add_scenario_btn = ft.FilledButton(
        TEMPLATE_ADD_BUTTON,
        style=ft.ButtonStyle(bgcolor=MTS_RED, color=MTS_WHITE),
        on_click=_add_scenario,
    )
    add_scenario_box = ft.Container(
        padding=ft.Padding.all(12),
        bgcolor=MTS_WHITE,
        border_radius=14,
        border=ft.Border.all(1, "#E8E8EA"),
        content=ft.Column(
            [
                ft.Text(TEMPLATE_ADD_TITLE, size=14, weight=ft.FontWeight.W_600, color=MTS_DARK),
                new_scenario_kind,
                new_scenario_name,
                new_scenario_text,
                add_scenario_btn,
            ],
            spacing=8,
            tight=True,
        ),
    )

    def _on_routing(_=None):
        _apply_effects()
        page.update()
        _push_settings()

    def _on_feature(_=None):
        _apply_effects()
        page.update()
        _push_settings()
        if history_check.value and hist_section.visible:
            _load_history(critical=hist_filter["critical"])
            page.update()

    def _on_templates(_=None):
        _sync_template_fields()
        _apply_effects()
        page.update()
        _push_settings()

    routing_dropdown.on_change = _on_routing
    scenarios_switch.on_change = _on_templates
    for box in setting_checks:
        box.on_change = _on_feature

    def _mark_tg_active(phone: str) -> None:
        tg_on["value"] = True
        tg_active.value = True
        tg_status_text.value = f"Активировано · {format_phone(phone)}"
        tg_status_text.color = MTS_RED
        page.update()

    def _stop_tg_poll() -> None:
        tg_on["stop"] = True

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

    def _poll_sleep(seconds: float) -> bool:
        """Ждём с проверкой stop; True — нужно выйти из цикла опроса."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if tg_on.get("stop"):
                return True
            time.sleep(0.2)
        return bool(tg_on.get("stop"))

    def _start_poll():
        if tg_on.get("polling"):
            return
        tg_on["stop"] = False
        tg_on["polling"] = True

        def loop():
            try:
                for _ in range(150):
                    if tg_on.get("stop"):
                        return
                    if _poll_once():
                        return
                    if _poll_sleep(1.5):
                        return
            finally:
                tg_on["polling"] = False

        # Не page.run_thread: executor Flet join'ится при выходе и вешает терминал.
        threading.Thread(target=loop, daemon=True, name="tg-status-poll").start()

    # url= — клиентский переход (телефон); on_click не дублируем (иначе 2 открытия).
    tg_open_btn = ft.FilledButton(
        TELEGRAM_OPEN_TEXT,
        icon=ft.Icons.TELEGRAM,
        url=_bot_start_url(""),
        style=ft.ButtonStyle(
            bgcolor=MTS_RED,
            overlay_color=MTS_RED_DARK,
            color=MTS_WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
        ),
    )
    _try_style = ft.ButtonStyle(
        bgcolor=MTS_DARK,
        color=MTS_WHITE,
        shape=ft.RoundedRectangleBorder(radius=12),
        padding=ft.Padding.symmetric(horizontal=20, vertical=14),
    )
    live_try_dash_btn = ft.FilledButton(
        TRY_SERVICE_TEXT,
        icon=ft.Icons.PHONE_IN_TALK,
        on_click=lambda e: _open_live_call(),
        style=_try_style,
    )
    live_try_btn = ft.FilledButton(
        TRY_SERVICE_TEXT,
        icon=ft.Icons.PHONE_IN_TALK,
        on_click=lambda e: _open_live_call(),
        style=_try_style,
    )
    live_call = LiveCallController(
        page=page,
        api_base=API_BASE,
        get_phone=lambda: connected_phone["value"],
        colors={"red": MTS_RED, "dark": MTS_DARK, "gray": MTS_GRAY, "white": MTS_WHITE},
        flet_port=int(os.getenv("FLET_PORT") or "8550"),
    )
    live_call_ref["ctl"] = live_call
    call_section = ft.Column(
        [live_call.build()],
        spacing=12,
        tight=True,
        visible=False,
        expand=True,
    )
    _sync_tg_open_url()

    disconnect_btn = ft.TextButton(
        DISCONNECT_BUTTON_TEXT,
        style=ft.ButtonStyle(color=MTS_RED),
        on_click=lambda e: disconnect_service(),
    )

    tab_dash = ft.FilledButton("Дашборд", on_click=lambda e: _show_tab("dash"))
    tab_hist = ft.FilledButton("История", on_click=lambda e: _show_tab("hist"))
    tab_call = ft.FilledButton("Звонок", on_click=lambda e: _open_live_call())
    tab_tpl = ft.FilledButton("Шаблоны", on_click=lambda e: _show_tab("tpl"))
    tab_set = ft.FilledButton("Настройки", on_click=lambda e: _show_tab("set"))
    hist_all_btn = ft.OutlinedButton(
        "Все",
        on_click=lambda e: (_load_history(critical=False), page.update()),
    )
    hist_crit_btn = ft.OutlinedButton(
        "Важные",
        on_click=lambda e: (_load_history(critical=True), page.update()),
    )
    refresh_hist_btn = ft.TextButton(
        "Обновить",
        on_click=lambda e: (
            _load_history(critical=hist_filter["critical"])
            if ui_tab["name"] == "hist"
            else _load_dashboard(),
            page.update(),
        ),
    )
    refresh_dash_btn = ft.TextButton(
        "Обновить",
        on_click=lambda e: (_load_dashboard(), page.update()),
    )

    dash_section = ft.Column(
        [
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("Дашборд линии", size=18, weight=ft.FontWeight.W_600, color=MTS_DARK),
                            ft.Text("Сводка по вашей линии — без чужих звонков", size=12, color=MTS_GRAY),
                        ],
                        spacing=2,
                        tight=True,
                        expand=True,
                    ),
                    refresh_dash_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            effect_banner,
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                bgcolor=MTS_WHITE,
                border_radius=16,
                border=ft.Border.all(1, "#E8E8EA"),
                content=ft.Column(
                    [
                        ft.Text("Живой диалог", size=15, weight=ft.FontWeight.W_600, color=MTS_DARK),
                        ft.Text(TRY_SERVICE_HINT, size=12, color=MTS_GRAY),
                        live_try_dash_btn,
                    ],
                    spacing=8,
                    tight=True,
                ),
            ),
            dash_body,
        ],
        spacing=12,
        tight=True,
        visible=True,
    )
    hist_section = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("История", size=16, weight=ft.FontWeight.W_600, color=MTS_DARK),
                    refresh_hist_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            history_off_hint,
            ft.Row([hist_all_btn, hist_crit_btn], spacing=8),
            history_list,
            detail_box,
        ],
        spacing=10,
        tight=True,
        visible=False,
    )
    tpl_section = ft.Column(
        [
            ft.Text(TEMPLATES_TAB_TITLE, size=16, weight=ft.FontWeight.W_600, color=MTS_DARK),
            ft.Text(TEMPLATES_HINT, size=13, color=MTS_GRAY),
            scenarios_switch,
            templates_off_hint,
            scenarios_status,
            scenarios_list,
            add_scenario_box,
            ft.Text(
                "Правки сохраняются при выходе из поля; для бота подтягиваются приветствие и FAQ.",
                size=12,
                color=MTS_GRAY,
            ),
        ],
        spacing=12,
        tight=True,
        visible=False,
    )

    routing_hint = ft.Text(ROUTING_HINT, size=12, color=MTS_GRAY)
    rules_block = ft.Column(
        [
            ft.Text(RULES_SECTION_TITLE, size=14, weight=ft.FontWeight.W_600, color=MTS_DARK),
            ft.Text(RULES_HINT, size=12, color=MTS_GRAY),
            rules_status,
            rules_list,
        ],
        spacing=8,
        tight=True,
    )

    set_section = ft.Column(
        [
            ft.Text("Настройки линии", size=16, weight=ft.FontWeight.W_600, color=MTS_DARK),
            routing_dropdown,
            routing_hint,
            ft.Text(FEATURES_TITLE, size=14, weight=ft.FontWeight.W_600, color=MTS_DARK),
            *setting_rows,
            effect_banner,
            ft.Text(
                "Изменения сразу влияют на приложение и бота.",
                size=12,
                color=MTS_GRAY,
            ),
            ft.Divider(height=1, color="#E8E8EA"),
            rules_block,
            ft.Divider(height=1, color="#E8E8EA"),
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                bgcolor=MTS_WHITE,
                border_radius=16,
                border=ft.Border.all(1, "#E8E8EA"),
                content=ft.Column(
                    [
                        ft.Text(
                            "Telegram-бот (опционально)",
                            size=15,
                            weight=ft.FontWeight.W_600,
                            color=MTS_DARK,
                        ),
                        ft.Row(
                            [tg_active, tg_status_text],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        tg_status_hint,
                        ft.Text(TELEGRAM_TOGGLE_HINT, size=13, color=MTS_GRAY),
                        tg_open_btn,
                        ft.Divider(height=1, color="#E8E8EA"),
                        ft.Text(TRY_SERVICE_HINT, size=13, color=MTS_GRAY),
                        live_try_btn,
                    ],
                    spacing=8,
                    tight=True,
                ),
            ),
            disconnect_btn,
        ],
        spacing=12,
        tight=True,
        visible=False,
    )

    # вторая ссылка на баннер в дашборде — одна и та же control нельзя в двух местах
    effect_banner_dash_text = ft.Text("", size=12, color=MTS_DARK)
    effect_banner_dash = ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        bgcolor="#FFF5F5",
        border_radius=12,
        border=ft.Border.all(1, "#F5C6C8"),
        content=effect_banner_dash_text,
    )
    dash_section.controls[1] = effect_banner_dash

    def _apply_effects_full():
        _sync_template_fields()
        text = _effect_summary()
        effect_banner_text.value = text
        effect_banner_dash_text.value = text
        history_off_hint.visible = not history_check.value
        hist_all_btn.disabled = not history_check.value
        hist_crit_btn.disabled = not history_check.value
        refresh_hist_btn.disabled = not history_check.value
        if not history_check.value:
            history_list.controls = [
                ft.Text(
                    "История выключена в настройках — включите «История звонков и саммари».",
                    size=13,
                    color=MTS_GRAY,
                )
            ]
            detail_box.visible = False
        tg_status_hint.value = (
            "Пуши в Telegram: только важные"
            if notify_critical_check.value
            else "Пуши в Telegram: все звонки (если бот подключён)"
        )

    _apply_effects = _apply_effects_full

    features_panel = ft.Container(
        visible=False,
        bgcolor=MTS_BG,
        padding=ft.Padding.symmetric(horizontal=24, vertical=16),
        content=ft.Column(
            [
                ft.Text(SERVICE_NAME, size=20, weight=ft.FontWeight.BOLD, color=MTS_DARK),
                ft.Row(
                    [tab_dash, tab_hist, tab_call, tab_tpl, tab_set],
                    spacing=8,
                    wrap=True,
                ),
                dash_section,
                hist_section,
                call_section,
                tpl_section,
                set_section,
            ],
            spacing=14,
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
        "history_check": history_check,
        "header_subtitle": header_subtitle,
        "back_btn": back_btn,
        "stage": stage,
        "dialog": details_dialog,
        "dialog_box": dialog_box,
        "tab_dash": tab_dash,
        "tab_hist": tab_hist,
        "tab_tpl": tab_tpl,
        "tab_set": tab_set,
        "dash_section": dash_section,
        "hist_section": hist_section,
        "tpl_section": tpl_section,
        "rules_block": rules_block,
        "set_section": set_section,
        "rules_list": rules_list,
        "rules_status": rules_status,
        "save_edit_btn": save_edit_btn,
        "detail_box": detail_box,
        "escalation_banner": escalation_banner,
        "routing_hint": routing_hint,
        "routing_dropdown": routing_dropdown,
        "scenarios_switch": scenarios_switch,
        "scenarios_list": scenarios_list,
        "scenarios_status": scenarios_status,
        "add_scenario_box": add_scenario_box,
        "add_scenario_btn": add_scenario_btn,
        "new_scenario_name": new_scenario_name,
        "new_scenario_text": new_scenario_text,
        "new_scenario_kind": new_scenario_kind,
        "history_list": history_list,
        "effect_banner": effect_banner_text,
        "effect_banner_box": effect_banner,
    }

    page.on_resize = lambda e: apply_responsive(e.width, e.height)
    page.on_close = lambda e: _stop_tg_poll()
    page.on_disconnect = lambda e: _stop_tg_poll()
    apply_responsive()


if __name__ == "__main__":
    # Веб-UI: http://0.0.0.0:8550 (для телефона нужен tunnel: DEMO_WEB_URL)
    # Desktop: FLET_VIEW=app python -m frontend.app
    # QR жюри по умолчанию → Telegram (scripts/make_demo_qr.py)
    import os

    view_raw = (os.getenv("FLET_VIEW") or "web").strip().lower()
    if view_raw in {"app", "desktop", "flet_app"}:
        view = ft.AppView.FLET_APP
    else:
        view = ft.AppView.WEB_BROWSER
    port = int(os.getenv("FLET_PORT") or "8550")
    host = os.getenv("FLET_HOST") or "0.0.0.0"
    # Flet 0.86: AUTO | CANVAS_KIT | SKWASM (HTML больше нет).
    # На телефоне первый заход тяжёлый (~10MB JS) — не «мертвый» сайт, а долгая загрузка.
    renderer_raw = (os.getenv("FLET_WEB_RENDERER") or "auto").strip().lower()
    renderer_map = {
        "auto": ft.WebRenderer.AUTO,
        "canvaskit": ft.WebRenderer.CANVAS_KIT,
        "canvas_kit": ft.WebRenderer.CANVAS_KIT,
        "skwasm": ft.WebRenderer.SKWASM,
    }
    web_renderer = renderer_map.get(renderer_raw, ft.WebRenderer.AUTO)
    print(
        f"Flet UI: view={view.value} renderer={web_renderer.value} "
        f"http://{host}:{port}/  (API_BASE={API_BASE})"
    )
    from pathlib import Path

    assets_dir = str(Path(__file__).resolve().parent / "assets")
    ft.run(
        main,
        view=view,
        host=host,
        port=port,
        web_renderer=web_renderer,
        assets_dir=assets_dir,
    )
