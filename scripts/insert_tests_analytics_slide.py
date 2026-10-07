"""Слайд #7 «Тесты и аналитика» — цифры проделанной работы (без CJM Ивана).

Пишет в docs/presentation_track1.pptx. Если файл занят — presentation_track1_pitch.pptx.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_presentation import (  # noqa: E402
    CARD,
    DARK,
    GRAY,
    MUTED,
    RED,
    WHITE,
    W,
    _bg,
    _card,
    _footer,
    _headline,
    _p,
    _rect,
    _round,
    _textbox,
)

PPTX = ROOT / "docs" / "presentation_track1.pptx"
FALLBACK = ROOT / "docs" / "presentation_track1_pitch.pptx"


def _clear_shapes(slide) -> None:
    for shape in list(slide.shapes):
        sp = shape._element
        sp.getparent().remove(sp)


def _stat(slide, left, top, width, height, number: str, label: str) -> None:
    _round(slide, left, top, width, height, CARD)
    _rect(slide, left, top, Inches(0.08), height, RED)
    nbox = _textbox(slide, left + Inches(0.2), top + Inches(0.18), width - Inches(0.35), Inches(0.55))
    _p(nbox.text_frame, number, size=28, bold=True, color=RED, space_after=0, first=True)
    lbox = _textbox(slide, left + Inches(0.2), top + Inches(0.72), width - Inches(0.35), Inches(0.45))
    _p(lbox.text_frame, label, size=12, color=GRAY, space_after=0, first=True)


def _draw_slide(slide, page: str) -> None:
    _clear_shapes(slide)
    _bg(slide)
    _rect(slide, 0, 0, W, Inches(0.42), RED)
    brand = _textbox(slide, Inches(0.55), Inches(0.06), Inches(10), Inches(0.32))
    _p(
        brand.text_frame,
        "StartUp Space VSTU",
        size=11,
        bold=True,
        color=WHITE,
        space_after=0,
        first=True,
    )
    _headline(
        slide,
        "Тесты и аналитика",
        "Покрыли автотестами почти весь продукт и прогнали голосом в реальных условиях.",
    )

    # Цифры сверху
    gap = Inches(0.25)
    w = Inches(3.9)
    y = Inches(1.7)
    h = Inches(1.25)
    _stat(slide, Inches(0.55), y, w, h, "14", "модулей автотестов — API, UI, TG, речь, live-call")
    _stat(slide, Inches(0.55) + w + gap, y, w, h, "60+", "сценариев в матрице маршрутизации")
    _stat(slide, Inches(0.55) + 2 * (w + gap), y, w, h, "100+", "проверок offline-suite без облака")

    _card(
        slide,
        Inches(0.55),
        Inches(3.2),
        Inches(6.0),
        Inches(3.2),
        "Что закрыли тестами",
        [
            "Контракты API, LLM, routing, шаблоны, hotline",
            "Live-call: VAD, barge-in, многоходовый диалог",
            "Flet UI + Telegram-дашборд + изоляция линий",
            "Fallback: Yandex недоступен → Whisper / edge-tts",
            "Аналитика: /calls/stats, critical / intent / action",
        ],
    )
    _card(
        slide,
        Inches(6.85),
        Inches(3.2),
        Inches(5.9),
        Inches(3.2),
        "Полевые прогоны",
        [
            "Шумное помещение: фон, эхо, чужая речь рядом",
            "Разные голоса, темп и громкость абонента",
            "Перебивание агента на полуслове (barge-in)",
            "Сеть с VPN / без Yandex — запасной STT/TTS",
            "E2E: приложение → звонок → история → правка",
        ],
    )
    _footer(slide, page)


def _find_slide_index(prs: Presentation) -> int | None:
    for i, slide in enumerate(prs.slides):
        for sh in slide.shapes:
            if hasattr(sh, "text") and "Тесты и аналитика" in (sh.text or ""):
                return i
    return None


def _renumber(prs: Presentation) -> None:
    pat = re.compile(r"^\d+/\d+$")
    total = len(prs.slides)
    for i, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            if not hasattr(sh, "text") or not sh.has_text_frame:
                continue
            t = (sh.text or "").strip()
            if not pat.match(t):
                continue
            sh.text_frame.clear()
            p = sh.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT
            run = p.add_run()
            run.text = f"{i}/{total}"
            run.font.size = Pt(10)
            run.font.color.rgb = MUTED
            run.font.name = "Arial"


def _save(prs: Presentation) -> Path:
    try:
        prs.save(str(PPTX))
        return PPTX
    except PermissionError:
        prs.save(str(FALLBACK))
        return FALLBACK


def main() -> Path:
    # Берём актуальный 9-слайдовый источник, если есть
    source = PPTX
    if FALLBACK.is_file():
        try:
            n_main = len(Presentation(str(PPTX)).slides) if PPTX.is_file() else 0
        except Exception:
            n_main = 0
        n_fb = len(Presentation(str(FALLBACK)).slides)
        if n_fb >= 9 and n_main < 9:
            source = FALLBACK

    prs = Presentation(str(source))
    idx = _find_slide_index(prs)
    if idx is None:
        blank = prs.slide_layouts[6]
        slide = prs.slides.add_slide(blank)
        sld_id_lst = prs.slides._sldIdLst
        ids = list(sld_id_lst)
        last = ids[-1]
        sld_id_lst.remove(last)
        sld_id_lst.insert(6, last)
        idx = 6
        slide = prs.slides[idx]
    else:
        slide = prs.slides[idx]

    total = len(prs.slides)
    _draw_slide(slide, f"{idx + 1}/{total}")
    _renumber(prs)
    return _save(prs)


if __name__ == "__main__":
    path = main()
    # Убираем временный pitch, если основной записан
    if path.resolve() == PPTX.resolve() and FALLBACK.is_file():
        try:
            FALLBACK.unlink()
            print(f"Removed {FALLBACK.name}")
        except PermissionError:
            print(f"Close PowerPoint/IDE tab and delete {FALLBACK.name} manually")
    prs = Presentation(str(path))
    print(f"Wrote {path} ({len(prs.slides)} slides)")
    for i, slide in enumerate(prs.slides, 1):
        titles = [
            sh.text.strip().split("\n")[0][:70]
            for sh in slide.shapes
            if hasattr(sh, "text") and sh.text.strip()
        ]
        label = titles[1] if len(titles) > 1 else (titles[0] if titles else "?")
        print(f"  {i}. {label}")
