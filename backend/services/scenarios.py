"""Шаблоны сценариев (ТЗ: редактирование сценариев — приветствие / FAQ)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from backend.config import ROOT_DIR
from backend.services.content_filter import clean_template

SCENARIOS_PATH = ROOT_DIR / "data" / "scenarios.json"


@dataclass
class Scenario:
    id: str
    name: str
    kind: str  # greeting | faq | custom
    text: str
    enabled: bool = True


DEFAULT_SCENARIOS: list[Scenario] = [
    Scenario(
        id="sc-greeting",
        name="Приветствие",
        kind="greeting",
        text=(
            "Здравствуйте! Вас слушает ИИ-секретарь компании Ивана Петрова. "
            "Я помогу с вопросами и при необходимости передам Ивану."
        ),
    ),
    Scenario(
        id="sc-faq-hours",
        name="FAQ: часы работы",
        kind="faq",
        text="Мы на связи в рабочие дни с 10:00 до 19:00 по Москве.",
    ),
    Scenario(
        id="sc-faq-callback",
        name="FAQ: перезвон",
        kind="faq",
        text="Если вопрос важный, Иван перезвонит в ближайшее время. Оставьте суть запроса.",
    ),
]


def _ensure() -> None:
    SCENARIOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SCENARIOS_PATH.is_file():
        save_scenarios(DEFAULT_SCENARIOS)


def load_scenarios() -> list[Scenario]:
    _ensure()
    raw = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    return [Scenario(**item) for item in raw]


def save_scenarios(items: list[Scenario]) -> None:
    SCENARIOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCENARIOS_PATH.write_text(
        json.dumps([asdict(s) for s in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_scenarios() -> list[dict[str, Any]]:
    return [asdict(s) for s in load_scenarios()]


def upsert_scenario(data: dict[str, Any]) -> dict[str, Any]:
    items = load_scenarios()
    sid = data.get("id") or f"sc-{uuid4().hex[:8]}"
    new = Scenario(
        id=sid,
        name=clean_template(str(data.get("name") or "")) or "Сценарий",
        kind=str(data.get("kind") or "custom"),
        text=clean_template(str(data.get("text") or "")),
        enabled=bool(data.get("enabled", True)),
    )
    for i, existing in enumerate(items):
        if existing.id == sid:
            items[i] = new
            save_scenarios(items)
            return asdict(new)
    items.append(new)
    save_scenarios(items)
    return asdict(new)


def delete_scenario(scenario_id: str) -> bool:
    items = load_scenarios()
    kept = [s for s in items if s.id != scenario_id]
    if len(kept) == len(items):
        return False
    save_scenarios(kept)
    return True


def get_greeting_text() -> str | None:
    for s in load_scenarios():
        if s.enabled and s.kind == "greeting":
            return clean_template(s.text)
    return None
