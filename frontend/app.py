"""Страница подключения услуги «ИИ-агент для звонков».

Flet 0.86 · стиль МТС · адаптив под десктоп, планшеты и мобильные экраны.

Запуск:  python -m frontend.app
"""

import webbrowser

import flet as ft

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
)

CARD_SIZE = 280            # карточка на десктопе
MOBILE_BREAKPOINT = 640    # ниже — маленький экран (телефон)
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

    # --- Обработчики (объявлены до использования в диалоге) ---------------
    def close_dialog(_=None):
        details_dialog.open = False
        page.update()

    def open_details(_=None):
        details_dialog.open = True
        page.update()

    def connect_service(_=None):
        # Без согласия на обработку данных услуга не подключается
        if not consent_checkbox.value:
            consent_checkbox.error = True
            consent_error.visible = True
            page.update()
            return
        consent_checkbox.error = False
        consent_error.visible = False
        close_dialog()
        header_subtitle.value = f"| {SERVICE_NAME}"
        page.title = f"МТС — {SERVICE_NAME}"
        features_panel.visible = True
        service_card.visible = False
        stage.controls.clear()
        stage.controls.append(features_panel)
        status_bar.content = ft.Row(
            [
                ft.Icon(ft.Icons.CHECK, color=MTS_RED, size=18),
                ft.Text(
                    f"{CONNECTED_STATUS}: «{SERVICE_NAME}»",
                    color=MTS_DARK,
                    weight=ft.FontWeight.W_600,
                ),
            ],
            spacing=8,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        page.update()

    def open_telegram(_=None):
        """Открывает бота в Telegram."""
        if not hasattr(page, "session"):
            page.launch_url(TELEGRAM_BOT_URL)
            return
        webbrowser.open(TELEGRAM_BOT_URL)

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

    # --- Карточка услуги (высота по контенту, без обрезки текста) --------
    header_icon_box = ft.Container(
        height=88,
        bgcolor=MTS_RED,
        border_radius=ft.BorderRadius(
            top_left=24,
            top_right=24,
            bottom_left=0,
            bottom_right=0,
        ),
        alignment=ft.Alignment.CENTER,
        content=ft.Text(SERVICE_ICON, size=40),
    )

    title_text = ft.Text(
        SERVICE_NAME,
        size=17,
        weight=ft.FontWeight.BOLD,
        color=MTS_DARK,
        text_align=ft.TextAlign.CENTER,
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

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

    service_card = ft.Container(
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
                header_icon_box,
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=20, vertical=16),
                    content=ft.Column(
                        [
                            title_text,
                            ft.Text(
                                SERVICE_TAGLINE,
                                size=12,
                                color=MTS_GRAY,
                                text_align=ft.TextAlign.CENTER,
                                max_lines=2,
                            ),
                            more_button,
                        ],
                        spacing=10,
                        alignment=ft.MainAxisAlignment.START,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                ),
            ],
            spacing=0,
            tight=True,
        ),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )

    # --- Статусная полоса ------------------------------------------------
    status_bar = ft.Container(
        bgcolor=MTS_WHITE,
        border=ft.Border(top=ft.BorderSide(1, "#E8E8EA")),
        content=ft.Text(
            "Подключите услугу — настройка займёт менее 5 минут",
            color=MTS_GRAY,
            size=13,
        ),
        padding=ft.Padding.symmetric(horizontal=8, vertical=10),
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

    tg_open_btn = ft.FilledButton(
        TELEGRAM_OPEN_TEXT,
        icon=ft.Icons.TELEGRAM,
        url=TELEGRAM_BOT_URL,
        style=ft.ButtonStyle(
            bgcolor=MTS_RED,
            overlay_color=MTS_RED_DARK,
            color=MTS_WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
        ),
        on_click=lambda e: open_telegram(),
    )

    features_panel = ft.Container(
        visible=True,
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
            ],
            spacing=12,
            tight=True,
        ),
    )

    # --- Шапка страницы --------------------------------------------------
    header_title = ft.Text(
        "МТС",
        size=22,
        weight=ft.FontWeight.BOLD,
        color=MTS_WHITE,
    )
    header_subtitle = ft.Text(
        f"| {HEADER_CONNECT_SUBTITLE}",
        size=15,
        color=MTS_WHITE,
    )
    header = ft.Container(
        bgcolor=MTS_RED,
        padding=ft.Padding.symmetric(horizontal=32, vertical=16),
        content=ft.Row(
            [
                header_title,
                header_subtitle,
            ],
            spacing=8,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    stage = ft.Column(
        [
            service_card,
        ],
        tight=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=16,
    )

    root = ft.Column(
        [
            header,
            stage,
            status_bar,
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
        card_w = max(240, min(CARD_SIZE, int(width * 0.88)))
        service_card.width = card_w
        header_icon_box.height = 72 if mobile else 88

        header.padding = ft.Padding.symmetric(
            horizontal=h_pad, vertical=12 if mobile else 16
        )
        status_bar.padding = ft.Padding.symmetric(horizontal=h_pad, vertical=10)
        header_title.size = 18 if mobile else 22

        more_button.style.padding = ft.Padding.symmetric(
            horizontal=32 if mobile else 24,
            vertical=14 if mobile else 10,
        )
        more_button.style.shape = ft.RoundedRectangleBorder(
            radius=14 if mobile else 12
        )

        dialog_box.width = min(420, max(240, width - 48))
        dialog_box.height = min(420, height - 200) if mobile else None

        features_panel.padding = ft.Padding.symmetric(horizontal=h_pad, vertical=16)

        page.update()

    page.ui = {
        "service_card": service_card,
        "features_panel": features_panel,
        "connect_btn": connect_btn,
        "consent": consent_checkbox,
        "consent_error": consent_error,
        "tg_open_btn": tg_open_btn,
        "setting_checks": setting_checks,
        "header_subtitle": header_subtitle,
        "stage": stage,
        "status_bar": status_bar,
        "dialog": details_dialog,
        "dialog_box": dialog_box,
    }

    page.on_resize = lambda e: apply_responsive(e.width, e.height)

    page.show_dialog(details_dialog)
    details_dialog.open = False
    apply_responsive()


if __name__ == "__main__":
    ft.run(main)
