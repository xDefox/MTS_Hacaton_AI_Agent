"""Настройки услуги по номеру МТС. Источник правды — фронт приложения."""

from __future__ import annotations

import json
import logging
from threading import Lock

from backend.config import ROOT_DIR
from backend.services.content_filter import clean_template
from backend.services.telegram_notify import normalize_phone

logger = logging.getLogger(__name__)

SETTINGS_PATH = ROOT_DIR / "data" / "service_settings.json"
_lock = Lock()

DEFAULTS = {
    "connected": False,       # услуга подключена в приложении МТС (персистентно)
    "routing": "voice",       # voice | chat | hybrid
    "history": True,          # история и саммари в боте
    "scenarios": True,        # использовать шаблоны ответов
    "hotline": True,          # эскалация на человека (заглушка в UI)
    "notify": "all",          # all | critical — пуши, если бот подключён
    "mode": "strict",         # strict | loyal
    "template_greeting": (
        "Здравствуйте! Вы говорите с виртуальным ассистентом. Чем могу помочь?"
    ),
    "template_faq": (
        "Часы работы: пн–пт 9–18.\n"
        "Доставка: 1–3 рабочих дня.\n"
        "По срочным вопросам оставьте контакт — перезвоним."
    ),
}

_TEMPLATE_KEYS = {"template_greeting", "template_faq"}
_MAX_TEMPLATE_LEN = 2000


def _load_all() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_all(data: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_settings(phone: str) -> dict:
    phone = normalize_phone(phone)
    out = dict(DEFAULTS)
    if not phone:
        return out
    with _lock:
        row = _load_all().get(phone) or {}
    for key in DEFAULTS:
        if key in row:
            out[key] = row[key]
    # Старые записи могли сохраниться до фильтра
    for key in _TEMPLATE_KEYS:
        out[key] = clean_template(str(out.get(key) or ""))
    # Старые записи без connected: раз номер есть в настройках — услуга уже подключалась
    if row and "connected" not in row:
        out["connected"] = True
    out["phone"] = phone
    return out


def update_settings(phone: str, **kwargs) -> dict:
    phone = normalize_phone(phone)
    if not phone:
        raise ValueError("empty phone")
    with _lock:
        data = _load_all()
        row = dict(DEFAULTS)
        row.update(data.get(phone) or {})
        for key, value in kwargs.items():
            if key not in DEFAULTS or value is None:
                continue
            if key == "routing" and value not in {"voice", "chat", "hybrid"}:
                continue
            if key in _TEMPLATE_KEYS:
                row[key] = clean_template(str(value or ""))[:_MAX_TEMPLATE_LEN]
                continue
            if key == "notify" and value not in {"all", "critical"}:
                continue
            if key == "mode" and value not in {"strict", "loyal"}:
                continue
            if key in {"connected", "history", "scenarios", "hotline"}:
                row[key] = bool(value)
            else:
                row[key] = value
        data[phone] = row
        _save_all(data)
    logger.info("Service settings updated phone=%s %s", phone, row)
    return get_settings(phone)
