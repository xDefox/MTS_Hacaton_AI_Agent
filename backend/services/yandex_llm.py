"""YandexGPT client via Yandex AI Studio SDK."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

from backend.config import Settings, get_settings
from backend.prompts.system_ivan import build_system_prompt
from backend.schemas import (
    ActionRequired,
    AgentLLMOutput,
    CallRequest,
    CallResponse,
    Intent,
    Priority,
)

logger = logging.getLogger(__name__)

# ТЗ / комплаенс: ровно одно предупреждение перед ответом (текст и голос/TTS)
AI_DISCLOSURE_PREFIX = (
    "Внимание: вы общаетесь с искусственным интеллектом. "
    "Разговор может записываться для передачи информации владельцу. "
)

# Типовые формулировки модели — срезаем с начала, чтобы не было дубля
_DISCLOSURE_HEAD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^внимание:\s*вы общаетесь с искусственным интеллектом\.?\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"^вы общаетесь с искусственным интеллектом\.?\s*",
        re.IGNORECASE,
    ),
    re.compile(r"^вы общаетесь с ии[^.]*\.?\s*", re.IGNORECASE),
    re.compile(
        r"^разговор может записываться[^.]*\.\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"^ваш звонок может быть записан[^.]*\.\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"^разговор может быть записан[^.]*\.\s*",
        re.IGNORECASE,
    ),
)


class YandexLLMError(RuntimeError):
    """Raised when the model call or JSON parsing fails after retries."""


def _strip_leading_disclosures(text: str) -> str:
    """Убирает повторные предупреждения об ИИ/записи с начала реплики."""
    cleaned = (text or "").strip()
    changed = True
    while changed and cleaned:
        changed = False
        for pattern in _DISCLOSURE_HEAD_PATTERNS:
            updated = pattern.sub("", cleaned, count=1).lstrip(" \n\t—–-")
            if updated != cleaned:
                cleaned = updated.strip()
                changed = True
    # «Здравствуйте! Здравствуйте!» → одно
    cleaned = re.sub(
        r"^(здравствуйте[!?.]?\s*){2,}",
        "Здравствуйте! ",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def ensure_ai_disclosure(agent_response: str) -> str:
    """Один канонический префикс + текст ответа без дублей."""
    text = _strip_leading_disclosures(agent_response)
    if not text:
        return AI_DISCLOSURE_PREFIX.strip()
    return f"{AI_DISCLOSURE_PREFIX}{text}"


def _build_messages(request: CallRequest, system_prompt: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "text": system_prompt}]

    if request.dialog_history:
        for turn in request.dialog_history:
            role = turn.get("role", "user")
            text = turn.get("text", "")
            if role in {"user", "assistant", "system"} and text:
                messages.append({"role": role, "text": text})

    phone = request.client_phone or "unknown"
    user_block = (
        f"session_id: {request.session_id}\n"
        f"client_phone: {phone}\n"
        f"caller_message: {request.user_message}"
    )
    messages.append({"role": "user", "text": user_block})
    return messages


def _extract_text(result: Any) -> str:
    """Normalize SDK result shapes to a single text string."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    text = getattr(result, "text", None)
    if isinstance(text, str) and text:
        return text
    try:
        # GPTModelResult is often indexable: result[0].text
        first = result[0]
        first_text = getattr(first, "text", None)
        if isinstance(first_text, str):
            return first_text
    except (TypeError, IndexError, KeyError):
        pass
    return str(result)


def _nonempty(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


_EN_JUNK = (
    "sentences for",
    "concrete next",
    "for ivan",
    "non-empty",
    "must be",
    "next step",
    "2-3 sentences",
    "caller message",
)


def _is_bad_text_field(value: str | None) -> bool:
    """Пусто / английский мусор / инструкция из промпта вместо ответа."""
    text = (value or "").strip()
    if not text:
        return True
    low = text.lower()
    if any(marker in low for marker in _EN_JUNK):
        return True
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    cyr = sum(1 for c in letters if "а" <= c.lower() <= "я" or c.lower() == "ё")
    return (cyr / len(letters)) < 0.35


def _default_next_step(action: str, is_critical: bool) -> str:
    mapping = {
        "transfer_to_human": "Срочно принять звонок или перезвонить",
        "callback_recommended": "Перезвонить клиенту в ближайшее время",
        "offer_telegram_chat": "Продолжить разбор в Telegram-чате",
        "continue_dialog": (
            "Проверить резюме" if is_critical else "Дождаться уточнения сути звонка"
        ),
    }
    return mapping.get(action, "Просмотреть резюме")


def _repair_truncated_json(text: str) -> str:
    """qwen2.5:3b часто обрывает JSON на num_predict — закрываем строку и скобки."""
    text = (text or "").strip()
    if not text:
        return text
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        text += '"'
    # убрать висячую запятую перед закрытием
    text = re.sub(r",\s*$", "", text)
    opens = text.count("{") - text.count("}")
    if opens > 0:
        text += "}" * opens
    return text


def _loads_json_lenient(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(cleaned)
        data = json.loads(repaired)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root is not an object")
    return data


def _parse_output(raw_text: str) -> AgentLLMOutput:
    data = _loads_json_lenient(raw_text)
    if isinstance(data, dict):
        # Маленькие модели часто отдают "" или копируют английские подсказки
        agent = _nonempty(data.get("agent_response"), "Здравствуйте! Чем могу помочь?")
        if _is_bad_text_field(agent):
            agent = "Здравствуйте! Чем могу помочь?"
        action = _nonempty(data.get("action_required"), "continue_dialog")
        is_critical = bool(data.get("is_critical", False))
        data["agent_response"] = agent
        data["caller_name"] = "" if data.get("caller_name") is None else str(data.get("caller_name"))
        next_step = str(data.get("recommended_next_step") or "").strip()
        if _is_bad_text_field(next_step):
            next_step = _default_next_step(action, is_critical)
        data["recommended_next_step"] = next_step
        summary = str(data.get("summary") or "").strip()
        if _is_bad_text_field(summary):
            summary = f"Обращение: {agent[:200]}" if agent else "Без резюме — уточнить цель звонка"
        data["summary"] = summary
        data.setdefault("is_critical", False)
        data.setdefault("priority", "normal")
        data.setdefault("intent", "other")
        data["action_required"] = action
    return AgentLLMOutput.model_validate(data)


# Внешний HTTP API YandexGPT (без gRPC SDK — на Windows gRPC часто ломается на IPv6).
YANDEX_COMPLETION_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def _run_yandex_sync(messages: list[dict[str, str]], settings: Settings) -> str:
    """Прямой REST к Yandex Cloud Foundation Models — как вчерашняя внешняя интеграция."""
    import httpx

    if not settings.yc_folder_id or not settings.yc_api_key:
        raise YandexLLMError("YC_FOLDER_ID and YC_API_KEY must be set in .env.")

    model_name = (settings.yandex_model or "yandexgpt").strip()
    version = (settings.yandex_model_version or "latest").strip()
    # rc/latest → в URI обычно latest; rc оставляем если явно задан
    ver = version if version not in {"", "rc"} else "latest"
    model_uri = f"gpt://{settings.yc_folder_id}/{model_name}/{ver}"

    # SDK ждал structured JSON через response_format — в REST просим явно в последнем user.
    payload = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": float(settings.yandex_temperature),
            "maxTokens": 800,
        },
        "messages": messages,
    }
    headers = {
        "Authorization": f"Api-Key {settings.yc_api_key}",
        "Content-Type": "application/json",
        "x-folder-id": settings.yc_folder_id,
    }

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(YANDEX_COMPLETION_URL, json=payload, headers=headers)
    except httpx.ConnectError as exc:
        raise YandexLLMError(
            "Нет доступа к llm.api.cloud.yandex.net (внешний YandexGPT). "
            "Включи VPN / другой интернет — с этой сети Yandex Cloud недоступен."
        ) from exc
    except httpx.HTTPError as exc:
        raise YandexLLMError(f"YandexGPT HTTP error: {exc}") from exc

    if response.status_code >= 400:
        raise YandexLLMError(
            f"YandexGPT HTTP {response.status_code}: {response.text[:400]}"
        )

    data = response.json()
    try:
        text = data["result"]["alternatives"][0]["message"]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise YandexLLMError(f"Unexpected YandexGPT response: {data!r}"[:400]) from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "YandexGPT HTTP ok latency_ms=%s chars=%s model=%s",
        latency_ms,
        len(text or ""),
        model_uri,
    )
    return text or ""


def _fallback_response(request: CallRequest, reason: str) -> CallResponse:
    """Safe degraded answer so the demo API stays alive if the model fails."""
    logger.warning("Using fallback response: %s", reason)
    text_lower = request.user_message.lower()
    wants_human = any(
        phrase in text_lower
        for phrase in ("соедините", "с менеджером", "с человеком", "с иваном", "оператор")
    )
    is_junk = _is_non_business_junk(request.user_message) and not wants_human
    is_critical = (not is_junk) and (
        wants_human
        or any(
            word in text_lower
            for word in ("срочно", "договор", "оплат", "жалоб", "мошен", "авария", "пилот")
        )
    )

    if wants_human:
        agent_response = "Понял вас. Соединяю с менеджером."
        action = ActionRequired.transfer_to_human
        intent = Intent.escalation
        summary = "Звонящий запросил соединение с человеком. Требуется срочная эскалация."
        next_step = "Принять звонок / перезвонить немедленно"
    elif is_junk:
        agent_response = (
            "Сейчас я принимаю рабочие обращения по компании. "
            "Если есть деловой вопрос — кратко опишите его, пожалуйста."
        )
        action = ActionRequired.continue_dialog
        intent = Intent.spam if any(
            w in text_lower for w in ("продаём", "предлагаем", "скидк", "реклам")
        ) else Intent.other
        summary = f"Нерабочее/спам обращение, без эскалации. Текст: {request.user_message[:200]}"
        next_step = "Игнорировать"
        is_critical = False
    elif is_critical:
        agent_response = (
            "Понимаю важность вопроса. Зафиксировал обращение и передам владельцу для быстрого перезвона."
        )
        action = ActionRequired.callback_recommended
        intent = Intent.support_request
        summary = f"Важное обращение. Текст: {request.user_message[:240]}"
        next_step = "Перезвонить сегодня"
    else:
        agent_response = (
            "Здравствуйте! Я помощник компании. Расскажите, пожалуйста, по какому вопросу звоните?"
        )
        action = ActionRequired.continue_dialog
        intent = Intent.other
        summary = f"Обычное обращение. Текст: {request.user_message[:240]}"
        next_step = "Просмотреть резюме в Telegram"

    return CallResponse(
        agent_response=ensure_ai_disclosure(agent_response),
        is_critical=is_critical,
        priority=(
            Priority.critical
            if wants_human
            else (Priority.high if is_critical else Priority.low if is_junk else Priority.normal)
        ),
        intent=intent,
        action_required=action,
        summary=summary,
        caller_name=None,
        recommended_next_step=next_step,
        session_id=request.session_id,
        model="fallback",
    )


def _is_non_business_junk(text: str) -> bool:
    """Оффтоп / холодные продажи / наживка «конфетка+менеджер» — не к специалисту."""
    from backend.services.routing_rules import (
        NON_BUSINESS_BAIT_MARKERS,
        has_business_context,
        has_human_request,
        is_human_bait_without_business,
    )

    if is_human_bait_without_business(text):
        return True
    t = (text or "").lower()
    # Чистая просьба человека без мусора — не junk
    if has_human_request(t) and has_business_context(t):
        return False
    if has_human_request(t) and not any(m in t for m in NON_BUSINESS_BAIT_MARKERS):
        return False
    return any(m in t for m in NON_BUSINESS_BAIT_MARKERS)


def _guard_non_business_escalation(request: CallRequest, response: CallResponse) -> CallResponse:
    """Если модель ошиблась и эскалировала мусор — принудительно снижаем."""
    if not _is_non_business_junk(request.user_message):
        return response
    if (
        response.action_required != ActionRequired.transfer_to_human
        and not response.is_critical
    ):
        return response

    logger.warning(
        "Guard: downgrade junk escalation session=%s action=%s critical=%s",
        request.session_id,
        response.action_required,
        response.is_critical,
    )
    text_lower = request.user_message.lower()
    intent = (
        Intent.spam
        if any(
            w in text_lower
            for w in (
                "прода",
                "предлага",
                "скидк",
                "реклам",
                "директ",
                "шины",
                "шину",
                "автошин",
            )
        )
        else Intent.other
    )
    return response.model_copy(
        update={
            "is_critical": False,
            "priority": Priority.low,
            "intent": intent,
            "action_required": ActionRequired.continue_dialog,
            "recommended_next_step": "Игнорировать / не перезванивать",
            "summary": (
                f"Нерабочее обращение (оффтоп/спам), эскалация отменена guard'ом. "
                f"Текст: {request.user_message[:200]}"
            ),
        }
    )


async def process_call_with_yandex(
    request: CallRequest,
    settings: Settings | None = None,
) -> CallResponse:
    settings = settings or get_settings()

    if not settings.yc_folder_id or not settings.yc_api_key:
        return _fallback_response(
            request,
            reason="YC_FOLDER_ID / YC_API_KEY not configured",
        )

    system_prompt = build_system_prompt(settings)
    messages = _build_messages(request, system_prompt)

    last_error: Exception | None = None
    attempts = 1 + max(0, settings.yandex_max_retries)

    for attempt in range(1, attempts + 1):
        try:
            if attempt > 1:
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "text": (
                            "Предыдущий ответ был невалидным JSON. "
                            "Верни строго один JSON-объект по схеме, без markdown."
                        ),
                    },
                ]

            raw = await asyncio.to_thread(_run_yandex_sync, messages, settings)
            parsed = _parse_output(raw)
            caller_name = parsed.caller_name.strip() or None
            response = CallResponse(
                agent_response=ensure_ai_disclosure(parsed.agent_response),
                is_critical=parsed.is_critical,
                priority=parsed.priority,
                intent=parsed.intent,
                action_required=parsed.action_required,
                summary=parsed.summary,
                caller_name=caller_name,
                recommended_next_step=parsed.recommended_next_step,
                session_id=request.session_id,
                model=f"{settings.yandex_model}:{settings.yandex_model_version}",
            )
            return _guard_non_business_escalation(request, response)
        except Exception as exc:  # noqa: BLE001 — last attempt falls back
            last_error = exc
            logger.exception("YandexGPT attempt %s/%s failed: %s", attempt, attempts, exc)

    return _fallback_response(request, reason=str(last_error) if last_error else "unknown")
