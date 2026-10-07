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
    # профиль ИТ-компании Ивана
    "разработ",
    "сайт",
    "приложени",
    "чат-бот",
    "телеграм-бот",
    "crm",
    "срм",
    "внедрен",
    "автоматизац",
    "проект",
    "по заказу",
    "лиценз",
    "тз ",
    "техзадан",
)

# Звонящий представился компанией — дело вероятно, но явный оффтоп важнее
_WEAK_BUSINESS_MARKERS: tuple[str, ...] = ("из компании", "компания ", "от компании")

# «Директ» как рекламный сервис, но не «директор»
_DIRECT_AD_MARKERS: tuple[str, ...] = (
    "директ ",
    "директ,",
    "директ.",
    "директе",
    "директу",
    "директа",
    "директом",
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
    *_DIRECT_AD_MARKERS,
    "seo",
    "продвижен",
    "кредитн",
    "розыгрыш",
    "выигрыш",
    "контекстн",
    "игнорируй",
    "system prompt",
    # чужие товары и бытовые вопросы — не к ИТ-компании
    "бензин",
    "топлив",
    "солярк",
    "дизел",
    "продукты",
    "пицц",
    "такси",
    "погода",
    "погоду",
    "погоды",
    "погоде",
)

HUMAN_REQUEST_MARKERS: tuple[str, ...] = (
    "соедините",
    "свяжите",
    "связать с",
    "позовите",
    "пригласите к телефону",
    "дайте менеджера",
    "с менеджером",
    "с человеком",
    "с иваном",
    "с руководител",
    "с директором",
    "с начальник",
    "оператор",
    "переведите на",
    "переключите",
    "живой человек",
)

# Слова, которые не несут темы звонка: вежливость, местоимения, сама просьба.
_NON_TOPIC_WORDS: frozenset[str] = frozenset(
    {
        "здравствуйте", "здравствуй", "привет", "добрый", "день", "вечер", "утро",
        "алло", "пожалуйста", "спасибо", "срочно", "быстрее", "скорее", "сейчас",
        "потом", "можно", "можете", "могли", "нужно", "нужен", "нужна", "надо",
        "хочу", "хотим", "хотел", "хотела", "хотели", "прошу", "просим", "лучше",
        "просто", "вот", "это", "мне", "нам", "нас", "вас", "вам", "меня", "мой",
        "наш", "все", "ещё", "еще", "тогда", "какой", "кого", "кем",
        "менеджер", "менеджера", "менеджером", "человек", "человеком", "человека",
        "иван", "ивана", "иваном", "оператор", "оператора", "оператором",
        "сотрудник", "сотрудником", "специалист", "специалистом", "руководитель",
        "руководителем", "директор", "директором", "начальник", "начальником",
        "живой", "живым", "соедините", "свяжите", "связать", "позовите",
        "переведите", "переключите", "пригласите", "дайте", "телефону",
    }
)

HumanRequestKind = str  # none | business | pure | bait | unclear


def _padded(text: str) -> str:
    return f" {(text or '').lower()} "


def has_business_context(text: str) -> bool:
    t = _padded(text)
    return any(m in t for m in BUSINESS_CONTEXT_MARKERS)


def has_human_request(text: str) -> bool:
    t = _padded(text)
    return any(m in t for m in HUMAN_REQUEST_MARKERS)


def _topic_words(text: str) -> list[str]:
    words = "".join(ch if ch.isalnum() else " " for ch in (text or "").lower()).split()
    return [w for w in words if len(w) > 2 and w not in _NON_TOPIC_WORDS]


def classify_human_request(text: str) -> HumanRequestKind:
    """Просьба соединить с человеком: насколько она по делу.

    business — есть дело компании (договор, пилот, разработка) → перевод;
    pure     — только просьба соединить, без темы → перевод;
    bait     — спам / оффтоп / чужой товар → не переводить;
    unclear  — есть посторонняя тема без дела → сначала уточнить цель.
    """
    if not has_human_request(text):
        return "none"
    if has_business_context(text):
        return "business"
    t = _padded(text)
    if any(m in t for m in NON_BUSINESS_BAIT_MARKERS):
        return "bait"
    if any(m in t for m in _WEAK_BUSINESS_MARKERS):
        return "business"
    if len(_topic_words(text)) >= 3:
        return "unclear"
    return "pure"


def is_human_bait_without_business(text: str) -> bool:
    """Просьба человека, которую не нужно сразу переводить (bait или unclear)."""
    return classify_human_request(text) in {"bait", "unclear"}


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
            "свяжите",
            "связать с",
            "позовите",
            "дайте менеджера",
            "с руководител",
            "с директором",
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
            *_DIRECT_AD_MARKERS,
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
            "ерунд",
            "бензин",
            "топлив",
            "пицц",
            "такси",
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
    text = _padded(user_message)
    kind = classify_human_request(user_message)
    bait = kind in {"bait", "unclear"}
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
    if kind == "unclear" and skipped_human:
        return RoutingRule(
            id="rule-human-unclear",
            name="Просьба человека без понятной цели",
            description="Сначала уточнить, касается ли вопрос дел компании",
            keywords=[],
            is_critical=False,
            intent="other",
            action_required="continue_dialog",
            enabled=True,
        )
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
