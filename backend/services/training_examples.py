"""Примеры обучения агента (ТЗ усиление: обучение на реальных разговорах).

Хранятся локально в data/training_examples.json и подмешиваются в system prompt.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
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


DEFAULT_EXAMPLES: list[TrainingExample] = [
    TrainingExample(
        id="ex-lead",
        user_message="Интересует пилот API до пятницы, компания Альфа",
        expected_intent="commercial",
        expected_action="callback_recommended",
        note="Коммерческий лид с дедлайном",
    ),
    TrainingExample(
        id="ex-spam",
        user_message="Предлагаем Директ со скидкой",
        expected_intent="spam",
        expected_action="continue_dialog",
        note="Холодные продажи",
    ),
    TrainingExample(
        id="ex-human",
        user_message="Соедините с менеджером по договору",
        expected_intent="escalation",
        expected_action="transfer_to_human",
        note="Горячая линия",
    ),
]


def _ensure() -> None:
    EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not EXAMPLES_PATH.is_file():
        save_examples(DEFAULT_EXAMPLES)


def load_examples() -> list[TrainingExample]:
    _ensure()
    raw = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))
    return [TrainingExample(**item) for item in raw]


def save_examples(items: list[TrainingExample]) -> None:
    EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLES_PATH.write_text(
        json.dumps([asdict(x) for x in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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


def examples_prompt_block(limit: int = 8) -> str:
    lines: list[str] = []
    for ex in load_examples():
        if not ex.enabled:
            continue
        lines.append(
            f'- «{ex.user_message}» → intent={ex.expected_intent}, '
            f"action={ex.expected_action}"
            + (f" ({ex.note})" if ex.note else "")
        )
        if len(lines) >= limit:
            break
    if not lines:
        return "- (примеров пока нет)"
    return "\n".join(lines)
