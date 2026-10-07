#!/usr/bin/env python3
"""Шаблоны владельца и «без повторного я ИИ».

Шаблоны и настройки линии пишутся во временные файлы — data/ не трогаем.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import get_settings  # noqa: E402
from backend.prompts.system_ivan import build_system_prompt  # noqa: E402
from backend.schemas import (  # noqa: E402
    ActionRequired,
    CallRequest,
    CallResponse,
    Intent,
    Priority,
)
from backend.services import scenarios as sc  # noqa: E402
from backend.services import service_settings as ss  # noqa: E402
from backend.services.call_agent import (  # noqa: E402
    _strip_self_intro,
    finalize_agent_reply,
    process_incoming_call,
)
from backend.services.yandex_llm import _build_messages, _fallback_response  # noqa: E402

LINE = "79990001234"
DISCLOSURE = "искусственным интеллектом"
USER_GREETING = "Добрый день! Студия Ивана, слушаю вас."
USER_HOURS = "Работаем пн-сб с 9 до 21, без обеда."
USER_PRICES = "Сайт-визитка от 40 000 рублей, чат-бот от 60 000."

failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failed
    if ok:
        print(f"OK   {name}")
    else:
        failed += 1
        print(f"FAIL {name}: {detail}")


def _seed_templates() -> dict[str, str]:
    sc.save_scenarios(sc.DEFAULT_SCENARIOS)
    greet = sc.upsert_scenario({"name": "Моё приветствие", "kind": "greeting", "text": USER_GREETING})
    hours = sc.upsert_scenario({"name": "Часы", "kind": "faq", "text": USER_HOURS})
    prices = sc.upsert_scenario({"name": "Цены", "kind": "faq", "text": USER_PRICES})
    return {"greeting": greet["id"], "hours": hours["id"], "prices": prices["id"]}


def test_priority() -> None:
    print("\n=== порядок / приоритет шаблонов ===")
    ids = _seed_templates()
    order = [s["id"] for s in sc.list_scenarios()]
    check("новые шаблоны выше стандартных", order.index(ids["hours"]) < order.index("sc-faq-hours"), str(order))
    check("приветствие пользователя активно", sc.get_greeting_text() == USER_GREETING, str(sc.get_greeting_text()))

    sc.upsert_scenario({"id": "sc-faq-hours", "name": "FAQ: часы работы", "kind": "faq",
                        "text": sc.DEFAULT_SCENARIOS[1].text, "enabled": False})
    order2 = [s["id"] for s in sc.list_scenarios()]
    check("выключение галочкой не меняет порядок", order2 == order, f"{order} -> {order2}")

    sc.upsert_scenario({"id": "sc-greeting", "name": "Приветствие", "kind": "greeting",
                        "text": "Здравствуйте! Новый текст по умолчанию."})
    check("отредактированный шаблон поднимается наверх", sc.list_scenarios()[0]["id"] == "sc-greeting")
    _seed_templates()


def test_profanity() -> None:
    print("\n=== мат в шаблонах ===")
    item = sc.upsert_scenario({"name": "Тест", "kind": "faq", "text": "Работаем, бля, до 18, нахуй."})
    check("мат вырезан при сохранении", "бля" not in item["text"] and "нах" not in item["text"], item["text"])
    check("смысл шаблона сохранён", "до 18" in item["text"], item["text"])
    sc.delete_scenario(item["id"])
    _seed_templates()


def test_faq_match() -> None:
    print("\n=== подбор шаблона по вопросу ===")
    cases = [
        ("Подскажите, до скольки вы работаете в субботу?", USER_HOURS),
        ("Сколько стоит сделать сайт?", USER_PRICES),
        ("Хочу чат-бот, какие цены?", USER_PRICES),
        ("Здравствуйте, подскажите пожалуйста", None),
    ]
    for question, expected in cases:
        got = sc.find_faq_answer(question)
        check(f"faq {question[:30]!r}", got == expected, f"got={got!r}")


def test_prompt_and_line_block() -> None:
    print("\n=== шаблоны в промпте и настройках линии ===")
    prompt = build_system_prompt(get_settings())
    check("шаблоны пользователя в промпте", USER_HOURS in prompt and USER_PRICES in prompt)
    check("пользовательский выше стандартного", prompt.find(USER_HOURS) < prompt.find("10:00 до 19:00"))

    ss.update_settings(LINE, scenarios=True, template_greeting=USER_GREETING,
                       template_faq=f"Часы: {USER_HOURS}\nЦены: {USER_PRICES}")
    req = CallRequest(session_id="tpl-line", user_message="Сколько стоит сайт?", line_phone=LINE)
    system = _build_messages(req, "SYS")[0]["text"]
    check("FAQ линии передан модели", USER_PRICES in system, system[-300:])
    check("приветствие линии помечено «не повторяй»", "не повторяй" in system)

    ss.update_settings(LINE, scenarios=False)
    system_off = _build_messages(req, "SYS")[0]["text"]
    check("шаблоны выключены → не передаются", USER_PRICES not in system_off)

    other = "79990005678"
    ss.update_settings(other, scenarios=True)
    system_default = _build_messages(
        CallRequest(session_id="tpl-def", user_message="Привет", line_phone=other), "SYS"
    )[0]["text"]
    check("стандартный FAQ («Доставка») не подставляется", "Доставка" not in system_default)
    ss.update_settings(LINE, scenarios=True)


def test_fallback_uses_template() -> None:
    print("\n=== ответ по шаблону без Яндекса ===")
    resp = _fallback_response(
        CallRequest(session_id="tpl-fb", user_message="До скольки вы работаете в субботу?", line_phone=LINE),
        "test",
    )
    check("fallback отвечает по шаблону", USER_HOURS in resp.agent_response, resp.agent_response)
    check("fallback intent=faq", resp.intent == Intent.faq, str(resp.intent))


def test_no_repeated_ai_intro() -> None:
    print("\n=== без повторного «я ИИ» ===")
    strip_cases = [
        ("Здравствуйте! Я ИИ-секретарь компании Ивана Петрова. Подскажите, по какому вопросу?",
         "Здравствуйте! Подскажите, по какому вопросу?"),
        ("Я ИИ-помощник, подскажите, пожалуйста, ваше имя?", "Подскажите, пожалуйста, ваше имя?"),
        ("Вы говорите с виртуальным ассистентом. Работаем с 9 до 18.", "Работаем с 9 до 18."),
        ("Понял вас. Передам Ивану, он перезвонит сегодня.", "Понял вас. Передам Ивану, он перезвонит сегодня."),
    ]
    for raw, expected in strip_cases:
        got = _strip_self_intro(raw)
        check(f"strip {raw[:28]!r}", got == expected, f"got={got!r}")

    model_reply = "Здравствуйте! Я ИИ-секретарь компании. Работаем пн-сб с 9 до 21."
    sid = f"tpl-ai-{uuid.uuid4().hex[:8]}"
    first = finalize_agent_reply(CallRequest(session_id=sid, user_message="Когда работаете?"), model_reply)
    check("1-я реплика: предупреждение ровно одно", first.lower().count(DISCLOSURE) == 1, first)
    check("1-я реплика: нет «я ИИ-секретарь»", "секретарь" not in first.lower(), first)

    history = [
        {"role": "assistant", "text": USER_GREETING},
        {"role": "user", "text": "Когда работаете?"},
        {"role": "assistant", "text": first},
    ]
    second = finalize_agent_reply(
        CallRequest(session_id=sid, user_message="А в воскресенье?", dialog_history=history),
        "Здравствуйте! Я виртуальный ассистент Ивана. В воскресенье выходной.",
    )
    check("2-я реплика: без предупреждения", DISCLOSURE not in second.lower(), second)
    check("2-я реплика: без самопредставления и «Здравствуйте»",
          second == "В воскресенье выходной.", second)

    asked = finalize_agent_reply(
        CallRequest(session_id=sid, user_message="Вы робот?", dialog_history=history),
        "Да, я виртуальный помощник Ивана, но всё передам ему лично.",
    )
    check("прямой вопрос «вы робот?» → честный ответ остаётся", "виртуальный" in asked, asked)

    asked_bot = finalize_agent_reply(
        CallRequest(session_id=sid, user_message="Я с ботом разговариваю?", dialog_history=history),
        "Да, я виртуальный помощник Ивана.",
    )
    check("«с ботом разговариваю?» → честный ответ остаётся", "виртуальный" in asked_bot, asked_bot)


async def _full_pipeline_two_turns() -> tuple[str, str]:
    reply = "Здравствуйте! Я ИИ-секретарь Ивана. Сайт-визитка от 40 000 рублей."

    async def fake(request, settings=None):
        return CallResponse(
            agent_response=reply, is_critical=False, priority=Priority.normal, intent=Intent.faq,
            action_required=ActionRequired.continue_dialog, summary="faq",
            recommended_next_step="-", session_id=request.session_id, model="mock",
        )

    sid = f"tpl-pipe-{uuid.uuid4().hex[:8]}"
    # Как в TG-демо и живом звонке: предупреждение звучит в самом приветствии
    greeting = f"Внимание: вы общаетесь с искусственным интеллектом. {USER_GREETING}"
    with patch("backend.services.call_agent.process_call_with_yandex", new=AsyncMock(side_effect=fake)):
        r1 = await process_incoming_call(CallRequest(session_id=sid, user_message="Сколько стоит сайт?",
                                                     dialog_history=[{"role": "assistant", "text": greeting}]))
        hist = [{"role": "assistant", "text": greeting},
                {"role": "user", "text": "Сколько стоит сайт?"},
                {"role": "assistant", "text": r1.agent_response}]
        r2 = await process_incoming_call(CallRequest(session_id=sid, user_message="А чат-бот?",
                                                     dialog_history=hist))
    return r1.agent_response, r2.agent_response


def test_pipeline() -> None:
    print("\n=== полный конвейер, 2 реплики ===")
    first, second = asyncio.run(_full_pipeline_two_turns())
    check("конвейер: после приветствия-с-предупреждением ответ без него", DISCLOSURE not in first.lower(), first)
    check("конвейер: приветствие не повторяется", "здравствуйте" not in first.lower(), first)
    check("конвейер: факт из шаблона на месте", "40 000" in first, first)
    check("конвейер: 2-я без предупреждения и «я ИИ»",
          DISCLOSURE not in second.lower() and "секретарь" not in second.lower(), second)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="tpl-test-"))
    with patch.object(sc, "SCENARIOS_PATH", tmp / "scenarios.json"), \
         patch.object(ss, "SETTINGS_PATH", tmp / "service_settings.json"):
        test_priority()
        test_profanity()
        test_faq_match()
        test_prompt_and_line_block()
        test_fallback_uses_template()
        test_no_repeated_ai_intro()
        test_pipeline()
    print()
    if failed:
        print(f"FAILED: {failed}")
        raise SystemExit(1)
    print("ALL TEMPLATE CHECKS OK")


if __name__ == "__main__":
    main()
