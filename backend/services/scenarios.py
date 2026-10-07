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
    # Порядок = приоритет: свежий шаблон пользователя первым, иначе
    # приветствие/FAQ по умолчанию перекрывают его (берётся первое включённое).
    for i, existing in enumerate(items):
        if existing.id == sid:
            content_changed = (existing.text, existing.kind) != (new.text, new.kind)
            if content_changed:
                items.pop(i)
                items.insert(0, new)
            else:
                items[i] = new
            save_scenarios(items)
            return asdict(new)
    items.insert(0, new)
    save_scenarios(items)
    return asdict(new)


# Один корень «работ» ловит и «часы работы», и «услуга не работает» — без контекста не считаем
_WEAK_ALONE_STEMS = frozenset({"работ", "дела", "услуг", "звонк", "вопрос", "помог", "скажи"})
_HOURS_HINTS = ("час", "скольк", "график", "режим", "открыт", "до сколь")


def find_faq_answer(question: str) -> str | None:
    """Ближайший FAQ/custom по *названию* шаблона (текст ответа в матч не входит)."""
    q_raw = (question or "").lower()
    words = {w for w in _words(question) if len(w) > 3}
    if not words:
        return None
    q_stems = {w[:5] for w in words}
    hours_ctx = any(h in q_raw for h in _HOURS_HINTS)
    best, best_score = None, 0
    for s in load_scenarios():
        if not s.enabled or s.kind == "greeting":
            continue
        text = clean_template(s.text)
        if not text:
            continue
        name_ws = [w for w in _words(s.name) if len(w) > 3]
        name_stems = {w[:5] for w in name_ws}
        if not name_stems:
            continue
        overlap = name_stems & q_stems
        score = len(overlap)
        if any(w in q_raw for w in name_ws if len(w) >= 5):
            score = max(score, 2)
        # «не работает услуга» ≠ «часы работы»
        if score and overlap <= _WEAK_ALONE_STEMS and not hours_ctx:
            score = 0
        if score == 1 and len(name_stems) >= 2 and overlap <= _WEAK_ALONE_STEMS and hours_ctx:
            score = 2  # «до скольки работаете» → шаблон «часы работы»
        need = 2 if len(name_stems) >= 2 else 1
        if score >= need and score > best_score:
            best, best_score = text, score
    return best if best_score >= 1 else None


_STOP_WORDS = frozenset(
    {
        "если", "можно", "пожалуйста", "здравствуйте", "скажите", "подскажите",
        "какие", "какой", "какая", "когда", "ваши", "ваша", "ваше", "вашей", "вашего",
        "есть", "меня", "этот", "этого", "хочу", "хотел", "хотела", "нужно", "очень",
        "алло", "моя", "мое", "моё", "мне",
    }
)


def _words(text: str) -> list[str]:
    words = "".join(ch if ch.isalnum() else " " for ch in (text or "").lower()).split()
    return [w for w in words if w not in _STOP_WORDS]


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
