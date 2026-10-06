"""Страница подключения услуги «ИИ-агент для звонков».

Flet 0.86 · стиль МТС · адаптив под десктоп, планшеты и мобильные экраны.

Запуск:  python -m frontend.app
"""

import flet as ft

from .assests import (
    MTS_RED,
    MTS_RED_DARK,
    MTS_DARK,
    MTS_GRAY,
    MTS_BG,
    MTS_WHITE,
    SERVICE_NAME,
    SERVICE_TAGLINE,
    SERVICE_ICON,
    SERVICE_DESCRIPTION,
    SERVICE_FEATURES,
    CONNECT_BUTTON_TEXT,
    MORE_BUTTON_TEXT,
    CONSENT_TEXT,
    CONSENT_DOCS,
    TELEGRAM_TOGGLE_TEXT,
    TELEGRAM_TOGGLE_HINT,
    FEATURES_TITLE,
    FEATURES,
    ROUTING_TITLE,
    ROUTING_VOICE,
    ROUTING_CHAT,
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


def main(page: ft.Page):
    page.title = "МТС — Подключение услуги"
    page.bgcolor = MTS_BG
    page.padding = 0

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
            consent_checkbox.error = "Подтвердите согласие, чтобы подключить услугу"
            page.update()
            return
        consent_checkbox.error = None
        close_dialog()
        # Показываем панель функций вместо карточки подключения
        service_card.visible = False
        features_panel.visible = True
        tg_note = (
            " · Telegram-бот подключён"
            if tg["connected"]
            else " · Telegram-бот: не подключён"
        )
        status_bar.content = ft.Row(
            [
                ft.Icon(ft.Icons.CHECK_CIRCLE, color=MTS_RED, size=18),
                ft.Text(
                    f"{CONNECTED_STATUS}: «{SERVICE_NAME}»{tg_note}",
                    color=MTS_DARK,
                    weight=ft.FontWeight.W_600,
                    expand=True,   # текст занимает строку и переносится
                ),
            ],
            spacing=8,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        page.update()

    # --- Согласие, Telegram-бот и кнопка подключения ---------------------
    def on_consent_change(e):
        """Кнопка «Подключить» тухнет, пока не принята оферта."""
        agreed = bool(e.control.value)
        connect_btn.opacity = 1.0 if agreed else 0.4
        if agreed:
            consent_checkbox.error = None
        page.update()

    consent_checkbox = ft.Checkbox(
        label=CONSENT_TEXT,
        value=False,
        active_color=MTS_RED,
        on_change=on_consent_change,
    )

    # Простая кнопка подключения Telegram-бота (тумблер по клику)
    tg = {"connected": False}
    tg_buttons = []
    tg_hints = []

    def toggle_tg(_=None):
        """Подключает/отключает Telegram-бота — меняет вид обеих кнопок."""
        tg["connected"] = not tg["connected"]
        for btn in tg_buttons:
            btn.style.bgcolor = MTS_DARK if tg["connected"] else MTS_RED
            btn.icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE if tg["connected"] else ft.Icons.ADD,
                color=MTS_WHITE,
            )
        for hint in tg_hints:
            hint.value = (
                "Бот подключён — уведомления и саммари будут приходить"
                if tg["connected"]
                else TELEGRAM_TOGGLE_HINT
            )
        page.update()

    def _make_tg_button() -> ft.FilledButton:
        return ft.FilledButton(
            TELEGRAM_TOGGLE_TEXT,
            icon=ft.Icon(ft.Icons.ADD, color=MTS_WHITE),
            style=ft.ButtonStyle(
                bgcolor=MTS_RED,
                overlay_color=MTS_RED_DARK,
                color=MTS_WHITE,
            ),
            on_click=lambda e: toggle_tg(),
        )

    tg_btn_dialog = _make_tg_button()
    tg_hint_dialog = ft.Text(TELEGRAM_TOGGLE_HINT, size=12, color=MTS_GRAY)
    tg_buttons.append(tg_btn_dialog)
    tg_hints.append(tg_hint_dialog)

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
                            ft.Icon(ft.Icons.CHECK_CIRCLE, color=MTS_RED, size=18),
                            ft.Text(f, size=14, color=MTS_DARK),
                        ],
                        spacing=8,
                    )
                    for f in SERVICE_FEATURES
                ],
                ft.Divider(height=1, color="#E8E8EA"),
                consent_checkbox,
                ft.Text(
                    CONSENT_DOCS,
                    size=12,
                    color=MTS_GRAY,
                ),
                ft.Divider(height=1, color="#E8E8EA"),
                tg_btn_dialog,
                tg_hint_dialog,
            ],
            spacing=12,
            tight=True,
            scroll=ft.ScrollMode.AUTO,  # контент прокручивается на узких экранах
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

    # --- Квадратная карточка услуги -------------------------------------
    header_icon_box = ft.Container(
        height=96,
        bgcolor=MTS_RED,
        border_radius=ft.BorderRadius(
            top_left=24,
            top_right=24,
            bottom_left=0,
            bottom_right=0,
        ),
        alignment=ft.Alignment.CENTER,
        content=ft.Text(SERVICE_ICON, size=44),
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
        height=CARD_SIZE,
        border_radius=24,
        bgcolor=MTS_WHITE,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=18,
            color="#1D1D1B22",
            offset=ft.Offset(0, 6),
        ),
        border=ft.Border(
            top=ft.BorderSide(width=1, color="#E8E8EA"),
            right=ft.BorderSide(width=1, color="#E8E8EA"),
            bottom=ft.BorderSide(width=1, color="#E8E8EA"),
            left=ft.BorderSide(width=1, color="#E8E8EA"),
        ),
        content=ft.Column(
            [
                header_icon_box,
                ft.Container(
                    padding=ft.Padding.all(16),
                    expand=True,
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
                            ft.Container(expand=True),
                            more_button,
                        ],
                        spacing=8,
                        alignment=ft.MainAxisAlignment.CENTER,
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
        content=ft.Text(
            "Подключите услугу — настройка займёт менее 5 минут",
            color=MTS_GRAY,
            size=13,
        ),
        padding=ft.Padding.symmetric(horizontal=8, vertical=8),
    )

    # --- Функции услуги (видны после подключения) ------------------------
    routing_group = ft.RadioGroup(
        value=ROUTING_VOICE,
        content=ft.Row(
            [
                ft.Radio(
                    value=ROUTING_VOICE,
                    label=ROUTING_VOICE_LABEL,
                    active_color=MTS_RED,
                ),
                ft.Radio(
                    value=ROUTING_CHAT,
                    label=ROUTING_CHAT_LABEL,
                    active_color=MTS_RED,
                ),
            ],
            spacing=16,
            tight=True,
        ),
    )

    def _feature_row(title: str, desc: str) -> ft.Container:
        """Строка функции услуги с переключателем вкл/выкл."""
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            bgcolor=MTS_WHITE,
            border_radius=16,
            border=ft.Border(
                top=ft.BorderSide(width=1, color="#E8E8EA"),
                right=ft.BorderSide(width=1, color="#E8E8EA"),
                bottom=ft.BorderSide(width=1, color="#E8E8EA"),
                left=ft.BorderSide(width=1, color="#E8E8EA"),
            ),
            content=ft.Row(
                [
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
                        expand=True,
                    ),
                    ft.Switch(value=True, active_color=MTS_RED),
                ],
                spacing=12,
                wrap=True,  # на узких экранах переключатель уходит ниже
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    # Та же кнопка Telegram-бота — после подключения (в панели функций)
    tg_btn_panel = _make_tg_button()
    tg_hint_panel = ft.Text(TELEGRAM_TOGGLE_HINT, size=12, color=MTS_GRAY, expand=True)
    tg_buttons.append(tg_btn_panel)
    tg_hints.append(tg_hint_panel)

    features_panel = ft.Container(
        visible=False,          # до подключения скрыта
        width=560,
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
                routing_group,
                *[_feature_row(t, d) for t, d in FEATURES],
                ft.Divider(height=1, color="#E8E8EA"),
                ft.Row(
                    [
                        tg_btn_panel,
                        tg_hint_panel,
                    ],
                    spacing=12,
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                "Все изменения вступают в силу сразу — без повторной настройки",
                    size=12,
                    color=MTS_GRAY,
                ),
            ],
            spacing=12,
        ),
    )

    # --- Шапка страницы --------------------------------------------------
    header_title = ft.Text(
        "МТС",
        size=22,
        weight=ft.FontWeight.BOLD,
        color=MTS_WHITE,
    )
    header = ft.Container(
        bgcolor=MTS_RED,
        padding=ft.Padding.symmetric(horizontal=32, vertical=16),
        content=ft.Row(
            [
                header_title,
                ft.Text("| Подключение услуги", size=15, color=MTS_WHITE),
            ],
            spacing=8,
            wrap=True,  # на узких экранах подпись переносится, а не вылезает
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    # --- Каркас страницы --------------------------------------------------
    # tight + scroll у корня: дети растянуты на всю ширину (шапка/статус
    # во весь экран), центр по центру, страница прокручивается при
    # переполнении. Связка Container(alignment) + Column(scroll) в центре
    # даёт известный баг Flet — серое поле вместо контента, поэтому её
    # здесь намеренно нет.
    center_box = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,  # карточка/панель по центру экрана
        content=ft.Column(
            [service_card, features_panel],
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    root = ft.Column(
        [
            header,
            center_box,
            status_bar,
        ],
        spacing=0,
        tight=True,
        scroll=ft.ScrollMode.AUTO,
        # Дети растянуты на всю ширину экрана (шапка/статус во весь экран)
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    page.add(root)

    # --- Адаптивность под размер экрана ----------------------------------
    def apply_responsive(width=None, height=None):
        """Пересчитывает размеры под текущий экран (мобильные/десктоп)."""
        width = width or getattr(page, "width", None) or 1100
        height = height or getattr(page, "height", None) or 720
        mobile = width <= MOBILE_BREAKPOINT

        # Горизонтальные отступы: компактные на телефоне
        h_pad = 16 if mobile else 32

        # Карточка вписывается и в ширину, и в высоту экрана
        card = max(220, min(CARD_SIZE, int(width * 0.85), int(height * 0.5)))
        service_card.width = card
        service_card.height = card

        # Шапка и статусная полоса
        header.padding = ft.Padding.symmetric(
            horizontal=h_pad, vertical=12 if mobile else 16
        )
        status_bar.padding = ft.Padding.symmetric(horizontal=h_pad, vertical=8)
        header_title.size = 18 if mobile else 22

        # Крупные тач-таргеты на мобильных
        more_button.style.padding = ft.Padding.symmetric(
            horizontal=32 if mobile else 24,
            vertical=14 if mobile else 10,
        )
        more_button.style.shape = ft.RoundedRectangleBorder(
            radius=14 if mobile else 12
        )

        # Диалог «Подробнее» не шире экрана и с прокруткой
        dialog_box.width = min(420, width - 48)
        dialog_box.height = min(380, height - 240) if mobile else None

        # Панель функций подстраивается под ширину экрана
        features_panel.width = min(560, width - 2 * h_pad)

        page.update()

    # Ссылки на ключевые контролы — для smoke-теста и отладки
    page.ui = {
        "service_card": service_card,
        "features_panel": features_panel,
        "connect_btn": connect_btn,
        "consent": consent_checkbox,
        "tg_state": tg,
        "tg_btn_dialog": tg_btn_dialog,
        "tg_btn_panel": tg_btn_panel,
        "tg_hint_dialog": tg_hint_dialog,
        "tg_hint_panel": tg_hint_panel,
        "status_bar": status_bar,
        "dialog": details_dialog,
    }

    page.on_resize = lambda e: apply_responsive(e.width, e.height)

    # Регистрируем диалог один раз и прячем его до нажатия «Подробнее»
    page.show_dialog(details_dialog)
    details_dialog.open = False
    apply_responsive()


if __name__ == "__main__":
    ft.run(main)