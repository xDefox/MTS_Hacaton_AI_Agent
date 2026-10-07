"""CRUD правил маршрутизации (ТЗ: контроль — настройка правил / сценарии)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from backend.config import ROOT_DIR

logger = logging.getLogger(__name__)

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


# Деловой контекст: «соедините с менеджером» честно; без него + спам/оффтоп = наживка.
BUSINESS_CONTEXT_MARKERS: tuple[str, ...] = (
    "договор",
    "оплат",
    "счёт",
    "счет",
    "пилот",
    "api",
    "интеграц",
    "sla",
    "nda",
    "жалоб",
    "претенз",
    "инцидент",
    "партнёр",
    "партнер",
    "кабинет",
    "поддерж",
    "коммерческ",
    " кп ",
    "кп до",
    "счёт",
    "встреч",
    "созвон",
    "дедлайн",
    "счет-фактур",
    "акт сверк",
    "по проекту",
    "по сделк",
)

NON_BUSINESS_BAIT_MARKERS: tuple[str, ...] = (
    "стишок",
    "стих",
    "анекдот",
    "поболтаем",
    "поболтать",
    "скучно",
    "сказк",
    "спой",
    "угадай",
    "развлеки",
    "конфет",
    "мороже",
    "игрушк",
    "котён",
    "котен",
    "щенк",
    "мем",
    "пранк",
    "шутк",
    "ерунд",
    "чушь",
    "глупост",
    "продаём",
    "продаем",
    "продаю",
    "продаёт",
    "продает",
    "шины",
    "шину",
    "шинами",
    "автошин",
    "резину",
    "резины",
    "предлагаем услуги",
    "хотим предложить",
    "скидк",
    "директ",
    "seo",
    "продвижен",
    "кредитн",
    "розыгрыш",
    "выигрыш",
    "контекстн",
    "игнорируй",
    "system prompt",
)

HUMAN_REQUEST_MARKERS: tuple[str, ...] = (
    "соедините",
    "с менеджером",
    "с человеком",
    "с иваном",
    "оператор",
    "переведите на",
    "переключите",
    "живой человек",
)


def has_business_context(text: str) -> bool:
    t = f" {(text or '').lower()} "
    return any(m in t for m in BUSINESS_CONTEXT_MARKERS)


def has_human_request(text: str) -> bool:
    t = (text or "").lower()
    return any(m in t for m in HUMAN_REQUEST_MARKERS)


def is_human_bait_without_business(text: str) -> bool:
    """«Соедините…» + спам/оффтоп без дела → не эскалировать.

    Конфетка/шины/мороженое/Директ и т.п. — наживка; чистая просьба
    человека или просьба + договор/оплата — горячая линия.
    """
    t = (text or "").lower()
    if not has_human_request(t):
        return False
    if has_business_context(t):
        return False
    return any(m in t for m in NON_BUSINESS_BAIT_MARKERS)


# Порядок важен: первое совпадение побеждает.
# Горячая линия — только с деловым контекстом; иначе смотрим спам/оффтоп.
DEFAULT_RULES: list[RoutingRule] = [
    RoutingRule(
        id="rule-human",
        name="Горячая линия",
        description="Просьба человека + деловой контекст → transfer_to_human",
        keywords=[
            "соедините с менеджером",
            "соедините с иваном",
            "с человеком",
            "оператор",
            "живой человек",
            "переведите на",
            "переключите",
        ],
        is_critical=True,
        intent="escalation",
        action_required="transfer_to_human",
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
        id="rule-complex-telegram",
        name="Сложный вопрос -> Telegram-чат",
        description="ТЗ: длинные/сложные -> offer_telegram_chat",
        keywords=[
            "детальное тз",
            "подробное тз",
            "sla",
            "nda",
            "интеграц",
            "1с",
            "этапы оплаты",
            "коммерческ",  # коммерческое / коммерческого предложения
            " кп ",
            "кп до",
        ],
        is_critical=True,
        intent="commercial",
        action_required="offer_telegram_chat",
    ),
    RoutingRule(
        id="rule-partner-lead",
        name="Партнёрский лид",
        description="Партнёрство / поставки → callback, не live-перевод",
        keywords=["партнёрств", "партнерств", "поставк"],
        is_critical=True,
        intent="partnership",
        action_required="callback_recommended",
    ),
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
            "продаю",
            "шины",
            "шину",
            "шинами",
            "автошин",
            "резину",
            "резины",
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
            "конфет",
            "мороже",
            "игрушк",
            "пранк",
            "мем",
            "ерунд",
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
        id="rule-noise",
        name="Шум линии",
        description="Ало/ммм без сути — не эскалировать",
        keywords=["ало", "слышно", "ммм", "эээ"],
        is_critical=False,
        intent="other",
        action_required="continue_dialog",
    ),
    RoutingRule(
        id="rule-faq-hours",
        name="FAQ: часы работы",
        description="Типовой FAQ — закрывать голосом без эскалации",
        keywords=["часы работы", "график работы", "во сколько открыты", "режим работы"],
        is_critical=False,
        intent="faq",
        action_required="continue_dialog",
    ),
    RoutingRule(
        id="rule-faq-callback",
        name="FAQ: перезвон",
        description="Вопрос про перезвон Ивана — FAQ, не escalation",
        keywords=[
            "перезвонит",
            "перезвоните",
            "оставлю вопрос",
            "если я оставлю",
        ],
        is_critical=False,
        intent="faq",
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
]


def save_rules(rules: list[RoutingRule]) -> None:
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(r) for r in rules]
    RULES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_rules_raw() -> list[RoutingRule]:
    raw = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return [RoutingRule(**item) for item in raw]


def merge_missing_defaults() -> None:
    """Добавить новые default-правила и обновить ключевые слова у известных id."""
    if not RULES_PATH.is_file():
        save_rules(DEFAULT_RULES)
        return
    existing = load_rules_raw()
    by_id = {r.id: r for r in existing}
    default_ids = {r.id for r in DEFAULT_RULES}
    # defaults first (актуальный порядок + keywords), затем кастом пользователя
    merged: list[RoutingRule] = []
    for rule in DEFAULT_RULES:
        if rule.id in by_id:
            custom = by_id[rule.id]
            # сохраняем enabled пользователя, остальное из DEFAULT
            merged.append(
                RoutingRule(
                    id=rule.id,
                    name=rule.name,
                    description=rule.description,
                    keywords=list(rule.keywords),
                    is_critical=rule.is_critical,
                    intent=rule.intent,
                    action_required=rule.action_required,
                    enabled=custom.enabled,
                )
            )
        else:
            merged.append(rule)
    for rule in existing:
        if rule.id not in default_ids:
            merged.append(rule)
    save_rules(merged)


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
    bait = is_human_bait_without_business(user_message)
    skipped_human = False
    for rule in load_rules():
        if not rule.enabled:
            continue
        if not any(kw in text for kw in rule.keywords):
            continue
        # Наживка «конфетка/шины/мороженое + соедините» — не rule-human
        if rule.id == "rule-human" and bait:
            skipped_human = True
            logger.info("Skip rule-human: no business context (bait) msg=%r", text[:120])
            continue
        return rule
    # Посторонняя тема + «соедините» без дела, и нет spam/offtopic-правила
    if bait and skipped_human:
        return RoutingRule(
            id="rule-human-bait",
            name="Наживка без делового контекста",
            description="Просьба человека без дела — не будить Ивана",
            keywords=[],
            is_critical=False,
            intent="other",
            action_required="continue_dialog",
            enabled=True,
        )
    return None
