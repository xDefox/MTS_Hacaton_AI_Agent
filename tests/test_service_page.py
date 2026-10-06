"""Тесты страницы подключения услуги (без запуска Flet-клиента).

Запуск напрямую:  python -m tests.test_service_page
Либо через pytest: pytest tests/
"""

from types import SimpleNamespace

from frontend.app import main as build_page


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
        self.added = []
        self.shown = []
        self.ui = None
        self.on_resize = None

    def add(self, *controls):
        self.added.extend(controls)

    def show_dialog(self, dialog):
        self.shown.append(dialog)
        dialog.open = True

    def update(self, *args, **kwargs):
        pass


def _page() -> _MockPage:
    page = _MockPage()
    build_page(page)
    return page


def test_page_built_and_dialog_hidden():
    page = _page()
    assert page.added, "контролы страницы не добавлены"
    assert page.shown, "диалог «Подробнее» не зарегистрирован"
    assert not page.shown[0].open, "диалог скрыт до нажатия «Подробнее»"
    assert page.window.width == 1100 and page.window.height == 720
    assert callable(page.on_resize), "обработчик on_resize не назначен"


def test_responsive_resize():
    page = _page()
    page.on_resize(SimpleNamespace(width=360, height=640))    # телефон
    page.on_resize(SimpleNamespace(width=768, height=1024))   # планшет
    page.on_resize(SimpleNamespace(width=1440, height=900))   # десктоп


def test_consent_gates_connect_button():
    """Кнопка подключения «тухнет» без согласия и оферту можно принять."""
    page = _page()
    ui = page.ui

    assert ui["consent"].value is False, "согласие не отмечено по умолчанию"
    assert not ui["connect_btn"].disabled, "кнопка остаётся кликабельной"
    assert ui["connect_btn"].opacity < 1.0, "без согласия кнопка «тухнет»"

    # Клик без согласия не подключает услугу и просит подтвердить оферту
    ui["connect_btn"].on_click(None)
    assert ui["service_card"].visible, "без согласия подключать нельзя"
    assert not ui["features_panel"].visible
    assert ui["consent"].error, "должна появиться подсказка про согласие"

    # Принимаем оферту — кнопка «расцветает», ошибка исчезает
    ui["consent"].value = True
    ui["consent"].on_change(SimpleNamespace(control=ui["consent"]))
    assert ui["connect_btn"].opacity == 1.0, "после согласия кнопка активна"
    assert ui["consent"].error is None, "подсказка исчезает"


def test_telegram_toggle_and_features_panel():
    """Переключатель Telegram переносится, панель функций заменяет карточку."""
    page = _page()
    ui = page.ui

    assert ui["features_panel"].visible is False

    # Выключаем Telegram-бота перед подключением
    ui["tg_switch"].value = False

    ui["consent"].value = True
    ui["consent"].on_change(SimpleNamespace(control=ui["consent"]))
    ui["connect_btn"].on_click(None)

    assert not ui["service_card"].visible, "карточка скрывается после подключения"
    assert ui["features_panel"].visible, "панель функций появляется"
    assert ui["tg_main_switch"].value is False, "состояние Telegram перенеслось"

    # TODO3: у панели есть заголовок и функции услуги
    panel_controls = ui["features_panel"].content.controls
    assert len(panel_controls) >= 5, "панель должна содержать функции услуги"


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