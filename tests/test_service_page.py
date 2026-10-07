"""Тесты страницы подключения услуги (без запуска Flet-клиента).

Запуск напрямую:  python -m tests.test_service_page
Либо через pytest: pytest tests/
"""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import flet as ft
import httpx
import pytest

from frontend.app import main as build_page
from frontend.assests import (
    AVAILABLE_TITLE,
    CATALOG_TITLE,
    CONNECTED_SECTION_TITLE,
    EDIT_SAVE_TEXT,
    ESCALATION_STUB,
    EXTRA_SERVICE_NAME,
    HEADER_CONNECT_SUBTITLE,
    LOGIN_TITLE,
    OPEN_BUTTON_TEXT,
    ROUTING_HINT,
    RULES_SECTION_TITLE,
    SERVICE_NAME,
    TELEGRAM_OPEN_TEXT,
    TEMPLATE_ADD_BUTTON,
    TEMPLATE_EMPTY,
)

# In-memory настройки услуги — без реального uvicorn
_FAKE_SETTINGS: dict[str, dict] = {}
_FAKE_RULES: list[dict] = []
_FAKE_SCENARIOS: list[dict] = []
_FAKE_PATCHES: list[dict] = []


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _default_rules() -> list[dict]:
    return [
        {
            "id": "rule-human",
            "name": "Человек",
            "description": "Просьба соединить с менеджером",
            "keywords": ["человека", "менеджер"],
            "is_critical": True,
            "intent": "request_human",
            "action_required": "transfer_to_human",
            "enabled": True,
        },
        {
            "id": "rule-spam",
            "name": "Спам",
            "description": "Реклама / не по делу",
            "keywords": ["реклама"],
            "is_critical": False,
            "intent": "spam",
            "action_required": "ignore",
            "enabled": True,
        },
    ]


def _default_scenarios() -> list[dict]:
    return [
        {
            "id": "sc-greeting",
            "name": "Приветствие",
            "kind": "greeting",
            "text": "Здравствуйте!",
            "enabled": True,
        },
        {
            "id": "sc-faq",
            "name": "Часы",
            "kind": "faq",
            "text": "С 10 до 19",
            "enabled": True,
        },
    ]


def _fake_httpx_get(url, params=None, timeout=None, **kwargs):
    params = params or {}
    path = urlparse(str(url)).path
    if path.endswith("/service/settings"):
        phone = "".join(c for c in str(params.get("phone") or "") if c.isdigit())
        row = dict(_FAKE_SETTINGS.get(phone) or {"connected": False})
        row["phone"] = phone
        return _FakeResp(200, row)
    if path.endswith("/telegram/status"):
        return _FakeResp(200, {"activated": False})
    if path.endswith("/routing_rules"):
        return _FakeResp(200, {"items": list(_FAKE_RULES)})
    if path.endswith("/scenarios"):
        return _FakeResp(200, {"items": list(_FAKE_SCENARIOS), "total": len(_FAKE_SCENARIOS)})
    if path.endswith("/calls/stats") or path.endswith("/stats"):
        return _FakeResp(
            200,
            {
                "total": 0,
                "critical": 0,
                "routine": 0,
                "critical_share": 0,
                "by_intent": {},
                "by_action": {},
            },
        )
    if "/calls" in path:
        return _FakeResp(200, {"items": [], "total": 0, "total_calls": 0})
    return _FakeResp(200, {})


def _fake_httpx_post(url, json=None, params=None, timeout=None, **kwargs):
    path = urlparse(str(url)).path
    body = json or {}
    if path.endswith("/service/settings"):
        phone = "".join(c for c in str(body.get("phone") or "") if c.isdigit())
        row = dict(_FAKE_SETTINGS.get(phone) or {})
        row.update({k: v for k, v in body.items() if k != "phone" and v is not None})
        _FAKE_SETTINGS[phone] = row
        out = dict(row)
        out["phone"] = phone
        return _FakeResp(200, out)
    return _FakeResp(200, {"ok": True})


def _fake_httpx_put(url, json=None, params=None, timeout=None, **kwargs):
    path = urlparse(str(url)).path
    body = json or {}
    if path.endswith("/routing_rules"):
        rid = body.get("id")
        for i, rule in enumerate(_FAKE_RULES):
            if rule.get("id") == rid:
                _FAKE_RULES[i] = {**rule, **body}
                return _FakeResp(200, _FAKE_RULES[i])
        _FAKE_RULES.append(dict(body))
        return _FakeResp(200, body)
    if path.endswith("/scenarios"):
        sid = body.get("id") or f"sc-new-{len(_FAKE_SCENARIOS)+1}"
        row = {
            "id": sid,
            "name": body.get("name") or "Шаблон",
            "kind": body.get("kind") or "custom",
            "text": body.get("text") or "",
            "enabled": bool(body.get("enabled", True)),
        }
        for i, item in enumerate(_FAKE_SCENARIOS):
            if item.get("id") == sid:
                _FAKE_SCENARIOS[i] = row
                return _FakeResp(200, row)
        _FAKE_SCENARIOS.append(row)
        return _FakeResp(200, row)
    return _FakeResp(200, body or {"ok": True})


def _fake_httpx_patch(url, json=None, params=None, timeout=None, **kwargs):
    path = urlparse(str(url)).path
    body = json or {}
    if "/calls/" in path:
        _FAKE_PATCHES.append({"path": path, "params": params or {}, "json": body})
        return _FakeResp(
            200,
            {
                "id": int(path.rstrip("/").split("/")[-1]),
                "input": body.get("user_message") or "",
                "output": body.get("agent_response") or "",
                "summary": body.get("summary") or "",
                "user_message": body.get("user_message") or "",
                "agent_response": body.get("agent_response") or "",
            },
        )
    return _FakeResp(200, body or {"ok": True})


def _fake_httpx_delete(url, params=None, timeout=None, **kwargs):
    path = urlparse(str(url)).path
    if "/scenarios/" in path:
        sid = path.rstrip("/").split("/")[-1]
        before = len(_FAKE_SCENARIOS)
        _FAKE_SCENARIOS[:] = [s for s in _FAKE_SCENARIOS if s.get("id") != sid]
        if len(_FAKE_SCENARIOS) == before:
            return _FakeResp(404, {"detail": "not found"})
        return _FakeResp(200, {"deleted": True, "id": sid})
    return _FakeResp(200, {"ok": True})


@pytest.fixture(autouse=True)
def _isolate_api(monkeypatch):
    _FAKE_SETTINGS.clear()
    _FAKE_RULES.clear()
    _FAKE_RULES.extend(_default_rules())
    _FAKE_SCENARIOS.clear()
    _FAKE_SCENARIOS.extend(_default_scenarios())
    _FAKE_PATCHES.clear()
    monkeypatch.setattr(httpx, "get", _fake_httpx_get)
    monkeypatch.setattr(httpx, "post", _fake_httpx_post)
    monkeypatch.setattr(httpx, "put", _fake_httpx_put)
    monkeypatch.setattr(httpx, "patch", _fake_httpx_patch)
    monkeypatch.setattr(httpx, "delete", _fake_httpx_delete)


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
    assert ui["dash_section"].visible, "после подключения открывается дашборд"
    assert not ui["set_section"].visible
    ui["tab_set"].on_click(None)
    assert ui["set_section"].visible
    assert ROUTING_HINT in (ui["routing_hint"].value or "")
    assert ui["setting_checks"], "должны быть чекбоксы настроек"
    assert all(isinstance(c, ft.Checkbox) for c in ui["setting_checks"])
    assert ui["tg_open_btn"] in _flatten(ui["features_panel"])
    assert ui["tg_open_btn"].content == TELEGRAM_OPEN_TEXT
    assert ui["tg_active"].value is False
    assert not getattr(ui["tg_open_btn"], "url", None), "url на кнопке открывает Telegram второй раз"

    ui["history_check"].value = False
    ui["history_check"].on_change(None)
    assert "История: выкл" in (ui["effect_banner"].value or "")
    ui["tab_hist"].on_click(None)
    assert ui["hist_section"].visible
    hist_text = " ".join(
        getattr(c, "value", "") or ""
        for c in _flatten(ui["history_list"])
        if isinstance(c, ft.Text)
    )
    assert "выключена" in hist_text.lower()

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


def test_service_persists_for_same_phone_on_relogin():
    """Повторный вход под тем же номером — услуга уже в «Подключённые»."""
    page = _page()
    ui = _enter_mts(page, phone="+7 900 222-33-44")
    ui["consent"].value = True
    ui["consent"].on_change(SimpleNamespace(control=ui["consent"]))
    ui["connect_btn"].on_click(None)
    ui["back_btn"].on_click(None)
    assert ui["connected_card"].visible
    assert "79002223344" in _FAKE_SETTINGS
    assert _FAKE_SETTINGS["79002223344"].get("connected") is True

    # «Новый» запуск приложения — тот же номер
    page2 = _page()
    ui2 = _enter_mts(page2, phone="+7 900 222-33-44")
    assert ui2["connected_card"].visible, "услуга должна восстановиться из настроек"
    assert not ui2["service_card"].visible
    assert not ui2["connected_empty"].visible


def test_templates_tab_can_add_scenario():
    """Вкладка Шаблоны: список сценариев + добавление нового."""
    page = _page()
    ui = _enter_mts(page)
    ui["consent"].value = True
    ui["consent"].on_change(SimpleNamespace(control=ui["consent"]))
    ui["connect_btn"].on_click(None)

    ui["tab_tpl"].on_click(None)
    assert ui["tpl_section"].visible
    assert ui["add_scenario_box"].visible
    assert ui["add_scenario_btn"].content == TEMPLATE_ADD_BUTTON
    listed = " ".join(
        getattr(c, "value", "") or ""
        for c in _flatten(ui["scenarios_list"])
        if isinstance(c, ft.Text) or isinstance(c, ft.TextField)
    )
    assert "Приветствие" in listed or "Здравствуйте" in listed
    assert TEMPLATE_EMPTY not in listed

    before = len(_FAKE_SCENARIOS)
    ui["new_scenario_name"].value = "Пилот"
    ui["new_scenario_text"].value = "Расскажите про сроки пилота"
    ui["new_scenario_kind"].value = "custom"
    ui["add_scenario_btn"].on_click(None)
    assert len(_FAKE_SCENARIOS) == before + 1
    assert any(s.get("name") == "Пилот" for s in _FAKE_SCENARIOS)
    assert "Сохранено" in (ui["scenarios_status"].value or "")

    ui["scenarios_switch"].value = False
    ui["scenarios_switch"].on_change(None)
    assert not ui["add_scenario_box"].visible
    assert not ui["scenarios_list"].visible


def test_rules_in_settings_and_call_edit_ui():
    """Правила внутри Настроек + правка карточки / заглушка эскалации."""
    page = _page()
    ui = _enter_mts(page)
    ui["consent"].value = True
    ui["consent"].on_change(SimpleNamespace(control=ui["consent"]))
    ui["connect_btn"].on_click(None)

    assert "tab_rules" not in ui, "отдельной вкладки Правила больше нет"
    ui["tab_set"].on_click(None)
    assert ui["set_section"].visible
    assert not ui["dash_section"].visible
    assert ui["rules_block"] in _flatten(ui["set_section"])
    section_text = " ".join(
        getattr(c, "value", "") or ""
        for c in _flatten(ui["set_section"])
        if isinstance(c, ft.Text)
    )
    assert RULES_SECTION_TITLE in section_text
    assert "Человек" in section_text
    assert "Спам" in section_text
    assert ROUTING_HINT in section_text

    boxes = [c for c in _flatten(ui["rules_list"]) if isinstance(c, ft.Checkbox)]
    assert len(boxes) >= 2, "должны быть переключатели правил"
    boxes[0].value = False
    boxes[0].on_change(SimpleNamespace(control=boxes[0]))
    assert any(not r.get("enabled", True) for r in _FAKE_RULES), "PUT должен сменить enabled"
    assert "выкл" in (ui["rules_status"].value or "")

    ui["tab_hist"].on_click(None)
    assert ui["hist_section"].visible
    assert ui["save_edit_btn"].content == EDIT_SAVE_TEXT
    assert not ui["detail_box"].visible
    assert ESCALATION_STUB in (ui["escalation_banner"].value or "")
    assert not ui["escalation_banner"].visible
    before = len(_FAKE_PATCHES)
    ui["save_edit_btn"].on_click(None)
    assert len(_FAKE_PATCHES) == before, "без выбранного звонка PATCH не шлём"


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
