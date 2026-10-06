"""CRUD правил маршрутизации (ТЗ: контроль — настройка правил / сценарии)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from backend.config import ROOT_DIR

RULES_PATH = ROOT_DIR / "data" / "routing_rules.json"


@dataclass
class RoutingRule:
    id: str
    name: str
    description: str
    keywords: list[str]
    is_critical: bool | None = None
    intent: str | None = None
    action_required: str | None = None
    enabled: bool = True


# Порядок важен: первое совпадение побеждает.
DEFAULT_RULES: list[RoutingRule] = [
    RoutingRule(
        id="rule-spam-ads",
        name="Холодные продажи / реклама",
        description="Не эскалировать спам и чужие услуги",
        keywords=[
            "директ",
            "скидк",
            "продвижен",
            "предлагаем услуги",
            "хотим предложить",
            "продаём",
            "продаем",
            "seo",
            "кредитн",
            "розыгрыш",
            "выигрыш",
            "контекстн",
        ],
        is_critical=False,
        intent="spam",
        action_required="continue_dialog",
    ),
    RoutingRule(
        id="rule-offtopic",
        name="Оффтоп",
        description="Стихи, болтовня — не к специалисту",
        keywords=[
            "стишок",
            "стих",
            "анекдот",
            "поболтаем",
            "поболтать",
            "скучно",
            "расскажи сказк",
            "спой",
            "угадай",
            "развлеки",
            "расскажи что-нибудь",
        ],
        is_critical=False,
        intent="other",
        action_required="continue_dialog",
    ),
    RoutingRule(
        id="rule-jailbreak",
        name="Jailbreak / injection",
        description="Попытки сломать промпт — не эскалировать",
        keywords=[
            "игнорируй",
            "забудь кто ты",
            "system prompt",
            "системный промпт",
            "без правил",
            "пиши пароль",
        ],
        is_critical=False,
        intent="other",
        action_required="continue_dialog",
    ),
    RoutingRule(
        id="rule-wrong-number",
        name="Ошибочный номер",
        description="Не туда позвонили",
        keywords=["ошибся номером", "не туда позвонил", "не тот номер", "ошибся телефоном"],
        is_critical=False,
        intent="wrong_number",
        action_required="continue_dialog",
    ),
    RoutingRule(
        id="rule-complaint",
        name="Жалоба / инцидент",
        description="Важное через callback, не всегда live-перевод",
        keywords=["жалоб", "претензи", "инцидент", "возмутительно"],
        is_critical=True,
        intent="complaint",
        action_required="callback_recommended",
    ),
    RoutingRule(
        id="rule-human",
        name="Горячая линия",
        description="Явная просьба человека → transfer_to_human",
        keywords=[
            "соедините с менеджером",
            "соедините с иваном",
            "с человеком",
            "оператор",
            "живой человек",
            "переведите на",
        ],
        is_critical=True,
        intent="escalation",
        action_required="transfer_to_human",
    ),
]


def save_rules(rules: list[RoutingRule]) -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(r) for r in rules]
    RULES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_rules_raw() -> list[RoutingRule]:
    raw = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return [RoutingRule(**item) for item in raw]


def merge_missing_defaults() -> None:
    if not RULES_PATH.is_file():
        save_rules(DEFAULT_RULES)
        return
    existing = load_rules_raw()
    have = {r.id for r in existing}
    added = False
    for rule in DEFAULT_RULES:
        if rule.id not in have:
            existing.append(rule)
            added = True
    if added:
        save_rules(existing)


def _ensure_file() -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not RULES_PATH.is_file():
        save_rules(DEFAULT_RULES)
        return
    merge_missing_defaults()


def load_rules() -> list[RoutingRule]:
    _ensure_file()
    return load_rules_raw()


def reset_rules_to_defaults() -> None:
    """Для тестов: полностью перезаписать файл дефолтами."""
    save_rules(DEFAULT_RULES)


def list_rules() -> list[dict[str, Any]]:
    return [asdict(r) for r in load_rules()]


def upsert_rule(data: dict[str, Any]) -> dict[str, Any]:
    rules = load_rules()
    rule_id = data.get("id") or f"rule-{uuid4().hex[:8]}"
    new_rule = RoutingRule(
        id=rule_id,
        name=str(data.get("name") or "Правило"),
        description=str(data.get("description") or ""),
        keywords=[str(k).lower() for k in (data.get("keywords") or [])],
        is_critical=data.get("is_critical"),
        intent=data.get("intent"),
        action_required=data.get("action_required"),
        enabled=bool(data.get("enabled", True)),
    )
    replaced = False
    for i, existing in enumerate(rules):
        if existing.id == rule_id:
            rules[i] = new_rule
            replaced = True
            break
    if not replaced:
        rules.append(new_rule)
    save_rules(rules)
    return asdict(new_rule)


def delete_rule(rule_id: str) -> bool:
    rules = load_rules()
    kept = [r for r in rules if r.id != rule_id]
    if len(kept) == len(rules):
        return False
    save_rules(kept)
    return True


def match_rule(user_message: str) -> RoutingRule | None:
    text = (user_message or "").lower()
    for rule in load_rules():
        if not rule.enabled:
            continue
        if any(kw in text for kw in rule.keywords):
            return rule
    return None
