"""Фильтр нецензурной лексики: шаблоны линии с фронта и ответы агента."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[а-яёa-z]+", re.IGNORECASE)

# «с» не берём в приставки корня «еб»: иначе «себе» → мат.
_EB_PREFIXES = (
    "", "на", "по", "за", "вы", "у", "до", "от", "при", "пере", "недо",
    "разъ", "объ", "подъ", "съ", "въ", "взъ", "изъ",
)
_HU_PREFIXES = ("", "на", "по", "от", "за", "ни", "пони")
_SUBSTRING_ROOTS = ("пизд", "бляд", "залуп", "шлюх", "долбоеб", "долбаеб", "гандон", "пидор", "пидар")
_PREFIX_ROOTS = ("мудак", "мудил", "мудозвон")
_EXACT_WORDS = {
    "бля", "сука", "суки", "суке", "суку", "сукой", "сучка", "сучара",
    "манда", "манды", "мандой",
}


def _is_profane(token: str) -> bool:
    t = token.lower().replace("ё", "е")
    if t in _EXACT_WORDS:
        return True
    if any(root in t for root in _SUBSTRING_ROOTS):
        return True
    if t.startswith(_PREFIX_ROOTS):
        return True
    for prefix in _EB_PREFIXES:
        if t.startswith(prefix + "еб") and len(t) > len(prefix) + 2:
            return True
    for prefix in _HU_PREFIXES:
        rest = t[len(prefix):] if t.startswith(prefix) else None
        if rest and len(rest) >= 3 and rest[:2] == "ху" and rest[2] in "йеияю":
            return True
    return False


def contains_profanity(text: str) -> bool:
    return any(_is_profane(m.group(0)) for m in _TOKEN_RE.finditer(text or ""))


def censor(text: str) -> str:
    """Заменить нецензурные слова на «***», остальной текст не трогать."""
    if not text:
        return text or ""
    return _TOKEN_RE.sub(lambda m: "***" if _is_profane(m.group(0)) else m.group(0), text)


def clean_template(text: str) -> str:
    """Шаблон линии без мата и без пустых «***»-хвостов."""
    cleaned = re.sub(r"\s*\*\*\*\s*", " ", censor(text))
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    cleaned = re.sub(r"([,;:])(\s*[,;:])+", r"\1", cleaned)
    cleaned = re.sub(r",(\s*[.!?])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip(" ,;:")
    if cleaned and (text or "")[:1].isupper():
        cleaned = cleaned[:1].upper() + cleaned[1:]
    return cleaned
