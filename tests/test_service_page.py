"""Тесты страницы подключения услуги (без запуска Flet-клиента).

Запуск напрямую:  python -m tests.test_service_page
Либо через pytest: pytest tests/
"""

from types import SimpleNamespace

import flet as ft

from frontend.app import main as build_page
from frontend.assests import (
    AVAILABLE_TITLE,
    CATALOG_TITLE,
    CONNECTED_SECTION_TITLE,
    EXTRA_SERVICE_NAME,
    HEADER_CONNECT_SUBTITLE,
    LOGIN_TITLE,
    OPEN_BUTTON_TEXT,
    SERVICE_NAME,
    TELEGRAM_OPEN_TEXT,
)


class _Window:
    width = 0
    height = 0


class _MockPage:
    """Минимальный прототип ft.Page для сборки дерева контроллов."""

    def __init__(self):
        self.window = _Window()
        self.title = ""
        self.bgcolor = None
        self.padding = 0
        self.theme = None
        self.added = []
        self.shown = []
        self.launched = []
        self.ui = None
        self.on_resize = None

    def add(self, *controls):
        self.added.extend(controls)

    def show_dialog(self, dialog):
        if dialog in self.shown and dialog.open:
            raise RuntimeError("Dialog is already opened")
        if dialog not in self.shown:
            self.shown.append(dialog)
        dialog.open = True

    def pop_dialog(self):
        if self.shown:
            dialog = self.shown[-1]
            dialog.open = False
            return dialog
        return None

    def launch_url(self, url):
        self.launched.append(url)

    def update(self, *args, **kwargs):
        pass


def _page() -> _MockPage:
    page = _MockPage()
    build_page(page)
    return page


def _enter_mts(page, phone="+7 900 111-22-33"):
    ui = page.ui
    ui["phone_field"].value = phone
    ui["login_btn"].on_click(None)
    return ui


def test_page_built_and_dialog_hidden():
    page = _page()
    assert page.added, "контролы страницы не добавлены"
    assert page.ui["dialog"] is not None
    assert not page.ui["dialog"].open, "диалог скрыт до нажатия «Подробнее»"
    assert page.window.width == 1100 and page.window.height == 720
    assert callable(page.on_resize), "обработчик on_resize не назначен"


def test_responsive_resize():
    page = _page()
    page.on_resize(SimpleNamespace(width=360, height=640))    # телефон
    assert page.ui["service_card"].width == 328, "на узком экране равные поля слева и справа"
    assert page.ui["extra_card"].width == 328
    page.on_resize(SimpleNamespace(width=768, height=1024))   # планшет
    page.on_resize(SimpleNamespace(width=1440, height=900))   # десктоп
    assert page.ui["service_card"].height is None, "карточка не должна быть квадратом фиксированной высоты"


def test_login_gate_asks_phone_first():
    """Запуск фронта — заглушка входа в приложение МТС, номер один раз."""
    page = _page()
    ui = page.ui
    assert LOGIN_TITLE in ui["header_subtitle"].value
    assert ui["login_gate"].visible
    assert not ui["catalog"].visible
    assert not ui["back_btn"].visible

    ui["login_btn"].on_click(None)
    assert ui["login_error"].visible, "без номера войти нельзя"
    assert ui["login_gate"].visible

    _enter_mts(page)
    assert HEADER_CONNECT_SUBTITLE in ui["header_subtitle"].value
    assert ui["catalog"].visible
    assert not ui["login_gate"].visible
    assert not ui["features_panel"].visible
    assert ui["profile"].visible
    assert "900" in (ui["profile_phone"].value or "")
    assert ui["service_card"].visible
    assert not ui["connected_card"].visible
    assert ui["connected_empty"].visible
    assert ui["service_card"] in _flatten(ui["catalog"])
    assert ui["extra_card"] in _flatten(ui["catalog"])
    catalog_text = " ".join(
        getattr(c, "value", "") or ""
        for c in _flatten(ui["catalog"])
        if isinstance(c, ft.Text)
    )
    assert CATALOG_TITLE in catalog_text
    assert AVAILABLE_TITLE in catalog_text
    assert CONNECTED_SECTION_TITLE in catalog_text
    assert EXTRA_SERVICE_NAME in catalog_text
    assert SERVICE_NAME in catalog_text


def test_consent_gates_connect_button():
    """Кнопка подключения «тухнет» без согласия и оферту можно принять."""
    page = _page()
    ui = _enter_mts(page)

    assert ui["consent"].value is False, "согласие не отмечено по умолчанию"
    assert not ui["connect_btn"].disabled, "кнопка остаётся кликабельной"
    assert ui["connect_btn"].opacity < 1.0, "без согласия кнопка «тухнет»"

    ui["connect_btn"].on_click(None)
    assert ui["service_card"].visible, "без согласия подключать нельзя"
    assert ui["catalog"].visible
    assert not ui["features_panel"].visible
    assert ui["consent"].error, "должна появиться подсказка про согласие"
    assert ui["consent_error"].visible

    ui["consent"].value = True
    ui["consent"].on_change(SimpleNamespace(control=ui["consent"]))
    assert ui["connect_btn"].opacity == 1.0, "после согласия кнопка активна"
    assert not ui["consent"].error
    assert not ui["consent_error"].visible

    ui["connect_btn"].on_click(None)
    assert ui["features_panel"].visible, "номер уже из входа"
    assert not ui["catalog"].visible


def test_feature_bullets_are_simple_checks():
    """Плюшки услуги — обычные галочки, не кружки и не пустые квадраты."""
    page = _page()
    dialog_column = page.ui["dialog_box"].content
    icons = [
        row.controls[0]
        for row in dialog_column.controls
        if isinstance(row, ft.Row) and row.controls and isinstance(row.controls[0], ft.Icon)
    ]
    assert icons, "в диалоге должны быть пункты услуги"
    for icon in icons:
        assert icon.icon == ft.Icons.CHECK, "плюшки — простые галочки"
        assert icon.icon != ft.Icons.CHECK_CIRCLE
        assert icon.icon != ft.Icons.CHECK_BOX_OUTLINE_BLANK
    texts = " ".join(
        getattr(c, "value", "") or ""
        for c in dialog_column.controls
        if isinstance(c, ft.Text)
    )
    assert "Telegram-бота" not in texts, "кнопка бота не в окне подключения"


def test_telegram_option_only_after_connect():
    """После подключения — название услуги, чеки настроек и переход в бота."""
    page = _page()
    ui = _enter_mts(page)

    dialog_column = ui["dialog_box"].content
    assert ui["tg_open_btn"] not in _flatten(dialog_column), "бота нет в окне подключения"
    assert HEADER_CONNECT_SUBTITLE in ui["header_subtitle"].value
    assert ui["catalog"].visible
    assert not ui["back_btn"].visible

    ui["consent"].value = True
    ui["consent"].on_change(SimpleNamespace(control=ui["consent"]))
    ui["connect_btn"].on_click(None)

    assert SERVICE_NAME in ui["header_subtitle"].value
    assert HEADER_CONNECT_SUBTITLE not in ui["header_subtitle"].value
    assert ui["features_panel"].visible
    assert not ui["catalog"].visible
    assert ui["back_btn"].visible
    assert ui["setting_checks"], "должны быть чекбоксы настроек"
    assert all(isinstance(c, ft.Checkbox) for c in ui["setting_checks"])
    assert ui["tg_open_btn"] in _flatten(ui["features_panel"])
    assert ui["tg_open_btn"].content == TELEGRAM_OPEN_TEXT
    assert ui["tg_active"].value is False
    assert not getattr(ui["tg_open_btn"], "url", None), "url на кнопке открывает Telegram второй раз"

    ui["tg_open_btn"].on_click(None)
    assert page.launched
    assert "start=79001112233" in page.launched[-1]
    assert page.launched.count(page.launched[-1]) == 1

    ui["back_btn"].on_click(None)
    assert ui["catalog"].visible
    assert not ui["features_panel"].visible
    assert not ui["back_btn"].visible
    assert HEADER_CONNECT_SUBTITLE in ui["header_subtitle"].value
    assert ui["connected_card"].visible, "после выхода услуга в «Подключённые»"
    assert not ui["service_card"].visible, "в «Доступных» её уже нет"
    assert not ui["connected_empty"].visible
    assert ui["open_btn"].content == OPEN_BUTTON_TEXT

    ui["open_btn"].on_click(None)
    assert ui["features_panel"].visible, "повторно «Подключить» не нужно"
    assert ui["back_btn"].visible

    ui["disconnect_btn"].on_click(None)
    assert ui["catalog"].visible
    assert ui["service_card"].visible
    assert not ui["connected_card"].visible
    assert ui["extra_card"].visible
    assert ui["tg_active"].value is False

    shown_before = len(page.shown)
    ui["dialog"].open = False
    ui["more_btn"].on_click(None)
    assert ui["dialog"].open, "после отключения снова «Подробнее»"
    assert len(page.shown) > shown_before

    ui["consent"].value = True
    ui["connect_btn"].on_click(None)
    assert ui["features_panel"].visible, "после отключения услугу можно подключить снова"
    assert ui["back_btn"].visible
    assert ui["tg_active"].value is False, "старый /start не включает ползунок сам"


def _flatten(control):
    found = [control]
    kids = getattr(control, "controls", None) or []
    inner = getattr(control, "content", None)
    if inner is not None and not isinstance(inner, str):
        kids = list(kids) + [inner]
    for child in kids:
        found.extend(_flatten(child))
    return found


def run_all():
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"ALL TESTS PASSED ({len(tests)})")


if __name__ == "__main__":
    run_all()
