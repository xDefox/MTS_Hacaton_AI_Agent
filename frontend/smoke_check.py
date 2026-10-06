"""Проверка построения UI страницы подключения без запуска Flet-клиента.

Запуск:  python frontend/smoke_check.py
Любая ошибка API Flet (AttributeError и т.п.) будет поймана здесь,
не дожидаясь открытия окна.
"""

import app


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

    def add(self, *controls):
        self.added.extend(controls)

    def show_dialog(self, dialog):
        self.shown.append(dialog)
        dialog.open = True

    def update(self, *args, **kwargs):
        pass


def main():
    from types import SimpleNamespace

    page = _MockPage()
    app.main(page)
    assert page.added, "контролы страницы не добавлены"
    assert page.shown, "диалог «Подробнее» не зарегистрирован"
    assert not page.shown[0].open, "диалог должен быть скрыт до нажатия «Подробнее»"
    assert page.window.width == 1100 and page.window.height == 720

    # Адаптивность: симулируем изменение размера экрана
    assert callable(page.on_resize), "обработчик on_resize не назначен"
    page.on_resize(SimpleNamespace(width=360, height=640))    # телефон
    page.on_resize(SimpleNamespace(width=768, height=1024))   # планшет
    page.on_resize(SimpleNamespace(width=1440, height=900))   # десктоп

    print("SMOKE OK - UI built, dialog hidden, responsive resize handled")


if __name__ == "__main__":
    main()