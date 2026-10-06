"""Страница подключения услуги «ИИ-агент для звонков».

Flet 0.86 · стиль МТС · адаптив под десктоп, планшеты и мобильные экраны.
"""

import flet as ft

from assests import (
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
        close_dialog()
        status_bar.content = ft.Row(
            [
                ft.Icon(ft.Icons.CHECK_CIRCLE, color=MTS_RED, size=18),
                ft.Text(
                    f"Услуга «{SERVICE_NAME}» подключена",
                    color=MTS_DARK,
                    weight=ft.FontWeight.W_600,
                ),
            ],
            spacing=8,
        )
        page.update()

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
            ft.FilledButton(
                CONNECT_BUTTON_TEXT,
                style=ft.ButtonStyle(
                    bgcolor=MTS_RED,
                    overlay_color=MTS_RED_DARK,
                    color=MTS_WHITE,
                ),
                on_click=lambda e: connect_service(e),
            ),
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
        ),
    )

    # --- Каркас страницы (со скроллом на маленьких экранах) ---------------
    center_box = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=service_card,
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

        page.update()

    page.on_resize = lambda e: apply_responsive(e.width, e.height)

    # Регистрируем диалог один раз и прячем его до нажатия «Подробнее»
    page.show_dialog(details_dialog)
    details_dialog.open = False
    apply_responsive()


if __name__ == "__main__":
    ft.run(main)