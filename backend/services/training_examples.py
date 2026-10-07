"""Примеры обучения агента (ТЗ усиление: обучение на реальных разговорах).

Хранятся локально в data/training_examples.json и подмешиваются в system prompt.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from typing import Any
from uuid import uuid4

from backend.config import ROOT_DIR

EXAMPLES_PATH = ROOT_DIR / "data" / "training_examples.json"


@dataclass
class TrainingExample:
    id: str
    user_message: str
    expected_intent: str
    expected_action: str
    note: str = ""
    enabled: bool = True
    is_critical: bool | None = None
    sample_reply: str = ""


DEFAULT_EXAMPLES: list[TrainingExample] = [
    TrainingExample(
        id="ex-lead",
        user_message="Интересует пилот API до пятницы, компания Альфа",
        expected_intent="commercial",
        expected_action="callback_recommended",
        note="Коммерческий лид с дедлайном",
        is_critical=True,
        sample_reply="Здравствуйте! Зафиксировала интерес к пилоту API. Как удобнее связаться и кто контакт с вашей стороны?",
    ),
    TrainingExample(
        id="ex-partner",
        user_message=(
            "Мы из SoftLine, обсуждаем партнёрство по поставкам, "
            "нужен ответ коммерческого предложения до среды"
        ),
        expected_intent="partnership",
        expected_action="callback_recommended",
        note="Партнёрский лид — не transfer_to_human без явной просьбы",
        is_critical=True,
        sample_reply="Здравствуйте! Приняла запрос по партнёрству и КП до среды. Передам Ивану — удобный телефон для ответа?",
    ),
    TrainingExample(
        id="ex-complex",
        user_message="Нужно детально обсудить SLA, NDA и интеграцию с 1С",
        expected_intent="commercial",
        expected_action="offer_telegram_chat",
        note="Сложный вопрос -> чат",
        is_critical=True,
        sample_reply="Здравствуйте! Тема объёмная — удобнее разобрать SLA и 1С в рабочем чате. Могу зафиксировать контакт?",
    ),
    TrainingExample(
        id="ex-spam",
        user_message="Предлагаем Директ со скидкой",
        expected_intent="spam",
        expected_action="continue_dialog",
        note="Холодные продажи",
        is_critical=False,
        sample_reply="Спасибо за предложение. Сейчас такие услуги не рассматриваем. Хорошего дня!",
    ),
    TrainingExample(
        id="ex-offtop",
        user_message="Расскажи стишок про кота",
        expected_intent="other",
        expected_action="continue_dialog",
        note="Оффтоп",
        is_critical=False,
        sample_reply="С удовольствием в другой раз — я по рабочим вопросам Ивана. Чем могу помочь по делу?",
    ),
    TrainingExample(
        id="ex-human",
        user_message="Соедините с менеджером по договору",
        expected_intent="escalation",
        expected_action="transfer_to_human",
        note="Горячая линия",
        is_critical=True,
        sample_reply="Конечно, организую соединение со специалистом. Останьтесь, пожалуйста, на линии.",
    ),
    TrainingExample(
        id="ex-faq",
        user_message="Подскажите ваши часы работы",
        expected_intent="faq",
        expected_action="continue_dialog",
        note="FAQ",
        is_critical=False,
        sample_reply="Мы на связи в рабочие дни с 10 до 19. Могу передать вопрос Ивану, если нужно подробнее.",
    ),
    TrainingExample(
        id="ex-noise",
        user_message="Ало? Меня слышно?",
        expected_intent="other",
        expected_action="continue_dialog",
        note="Шум линии",
        is_critical=False,
        sample_reply="Да, слышу вас. Подскажите, пожалуйста, цель звонка.",
    ),
    TrainingExample(
        id="ex-wrong",
        user_message="Извините, я ошибся номером",
        expected_intent="wrong_number",
        expected_action="continue_dialog",
        note="Ошибочный номер",
        is_critical=False,
        sample_reply="Ничего страшного. Всего доброго!",
    ),
    TrainingExample(
        id="ex-complaint",
        user_message="Хочу подать жалобу, это инцидент",
        expected_intent="complaint",
        expected_action="callback_recommended",
        note="Жалоба",
        is_critical=True,
        sample_reply="Понимаю, как это важно. Зафиксирую обращение — Иван свяжется. Оставьте, пожалуйста, контакт.",
    ),
    TrainingExample(
        id="ex-support",
        user_message="Не могу зайти в личный кабинет, ошибка доступа",
        expected_intent="support_request",
        expected_action="continue_dialog",
        note="Поддержка",
        is_critical=False,
        sample_reply="Поняла. Уточните, пожалуйста, текст ошибки и логин — передам в поддержку или Ивану.",
    ),
    TrainingExample(
        id="ex-payment",
        user_message="Проблема по оплате счёта, срочно нужен Иван",
        expected_intent="support_request",
        expected_action="transfer_to_human",
        note="Срочная оплата + человек",
        is_critical=True,
        sample_reply="Слышу, срочный вопрос по оплате. Соединяю с Иваном — останьтесь на линии.",
    ),
]


def save_examples(items: list[TrainingExample]) -> None:
    EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLES_PATH.write_text(
        json.dumps([asdict(x) for x in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_examples_raw() -> list[TrainingExample]:
    raw = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))
    out: list[TrainingExample] = []
    for item in raw:
        item = dict(item)
        item.setdefault("is_critical", None)
        item.setdefault("sample_reply", "")
        # игнор лишних ключей из старых файлов
        allowed = {f.name for f in fields(TrainingExample)}
        out.append(TrainingExample(**{k: v for k, v in item.items() if k in allowed}))
    return out


def sync_default_examples() -> None:
    """Обновить/добавить default-примеры по id (кастом пользователя сохраняем)."""
    EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not EXAMPLES_PATH.is_file():
        save_examples(DEFAULT_EXAMPLES)
        return
    existing = load_examples_raw()
    by_id = {e.id: e for e in existing}
    default_ids = {e.id for e in DEFAULT_EXAMPLES}
    merged: list[TrainingExample] = []
    for ex in DEFAULT_EXAMPLES:
        if ex.id in by_id:
            custom = by_id[ex.id]
            merged.append(
                TrainingExample(
                    id=ex.id,
                    user_message=ex.user_message,
                    expected_intent=ex.expected_intent,
                    expected_action=ex.expected_action,
                    note=ex.note,
                    enabled=custom.enabled,
                    is_critical=ex.is_critical,
                    sample_reply=ex.sample_reply or custom.sample_reply,
                )
            )
        else:
            merged.append(ex)
    for ex in existing:
        if ex.id not in default_ids:
            merged.append(ex)
    save_examples(merged)


def _ensure() -> None:
    sync_default_examples()


def load_examples() -> list[TrainingExample]:
    _ensure()
    return load_examples_raw()


def reset_examples_to_defaults() -> None:
    save_examples(DEFAULT_EXAMPLES)


def list_examples() -> list[dict[str, Any]]:
    return [asdict(x) for x in load_examples()]


def upsert_example(data: dict[str, Any]) -> dict[str, Any]:
    items = load_examples()
    eid = data.get("id") or f"ex-{uuid4().hex[:8]}"
    new = TrainingExample(
        id=eid,
        user_message=str(data.get("user_message") or ""),
        expected_intent=str(data.get("expected_intent") or "other"),
        expected_action=str(data.get("expected_action") or "continue_dialog"),
        note=str(data.get("note") or ""),
        enabled=bool(data.get("enabled", True)),
        is_critical=data.get("is_critical"),
        sample_reply=str(data.get("sample_reply") or ""),
    )
    for i, existing in enumerate(items):
        if existing.id == eid:
            items[i] = new
            save_examples(items)
            return asdict(new)
    items.append(new)
    save_examples(items)
    return asdict(new)


def delete_example(example_id: str) -> bool:
    items = load_examples()
    kept = [x for x in items if x.id != example_id]
    if len(kept) == len(items):
        return False
    save_examples(kept)
    return True


def examples_prompt_block(limit: int = 16) -> str:
    lines: list[str] = []
    items = load_examples()
    default_ids = {e.id for e in DEFAULT_EXAMPLES}
    # Сначала кастом Ивана, потом дефолты — иначе лимит срежет новые примеры
    ordered = [e for e in items if e.id not in default_ids] + [
        e for e in items if e.id in default_ids
    ]
    for ex in ordered:
        if not ex.enabled:
            continue
        crit = ""
        if ex.is_critical is not None:
            crit = f", is_critical={str(ex.is_critical).lower()}"
        reply = f' | reply: «{ex.sample_reply}»' if ex.sample_reply else ""
        lines.append(
            f'- «{ex.user_message}» → intent={ex.expected_intent}, '
            f"action={ex.expected_action}{crit}"
            + (f" ({ex.note})" if ex.note else "")
            + reply
        )
        if len(lines) >= limit:
            break
    if not lines:
        return "- (примеров пока нет)"
    return "\n".join(lines)
