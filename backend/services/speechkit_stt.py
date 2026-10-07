"""Yandex SpeechKit STT (sync recognize) + helper TTS for demo samples."""

from __future__ import annotations

import logging
from typing import Literal

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

AudioFormat = Literal["oggopus", "lpcm"]


class SpeechKitError(Exception):
    """SpeechKit API / config error."""


def _auth_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.yc_api_key:
        raise SpeechKitError("YC_API_KEY must be set in .env for SpeechKit.")
    return {"Authorization": f"Api-Key {settings.yc_api_key}"}


def guess_audio_format(filename: str | None, content_type: str | None) -> AudioFormat:
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    if name.endswith((".wav", ".raw", ".pcm")) or "wav" in ctype or "lpcm" in ctype:
        return "lpcm"
    return "oggopus"


async def transcribe_audio(
    audio: bytes,
    *,
    audio_format: AudioFormat = "oggopus",
    lang: str = "ru-RU",
    sample_rate_hertz: int | None = None,
) -> str:
    """
    Sync STT via SpeechKit API v1.
    Limits: ~1 MB, short utterances (demo / one phrase).
    """
    if not audio:
        raise SpeechKitError("Empty audio payload.")
    if len(audio) > 1_000_000:
        raise SpeechKitError("Audio too large for sync STT (max ~1 MB).")

    settings = get_settings()
    if not settings.yc_folder_id:
        raise SpeechKitError("YC_FOLDER_ID must be set in .env for SpeechKit.")

    params: dict[str, str] = {
        "lang": lang,
        "topic": settings.stt_topic or "general",
        "format": audio_format,
        "folderId": settings.yc_folder_id,
    }
    if audio_format == "lpcm":
        params["sampleRateHertz"] = str(sample_rate_hertz or 16000)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=8.0)) as client:
            response = await client.post(
                STT_URL,
                params=params,
                content=audio,
                headers=_auth_headers(),
            )
    except httpx.ConnectError as exc:
        raise SpeechKitError(
            "Нет доступа к Yandex SpeechKit (stt.api.cloud.yandex.net). "
            "Проверь интернет/VPN/firewall — без внешней сети Yandex не работает."
        ) from exc
    except httpx.HTTPError as exc:
        raise SpeechKitError(f"SpeechKit STT network error: {exc}") from exc

    if response.status_code >= 400:
        logger.error("SpeechKit STT error %s: %s", response.status_code, response.text)
        raise SpeechKitError(f"SpeechKit STT failed: {response.status_code} {response.text}")

    payload = response.json()
    text = (payload.get("result") or "").strip()
    if not text:
        raise SpeechKitError("SpeechKit returned empty transcript.")
    logger.info("STT ok chars=%s", len(text))
    return text


async def synthesize_ogg(text: str, *, voice: str = "alena", lang: str = "ru-RU") -> bytes:
    """TTS → OggOpus bytes (для smoke / демо без микрофона)."""
    settings = get_settings()
    if not settings.yc_folder_id:
        raise SpeechKitError("YC_FOLDER_ID must be set in .env for SpeechKit.")

    data = {
        "text": text,
        "lang": lang,
        "voice": voice,
        "folderId": settings.yc_folder_id,
        "format": "oggopus",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=15.0)) as client:
            response = await client.post(
                TTS_URL,
                data=data,
                headers=_auth_headers(),
            )
    except httpx.ConnectError as exc:
        raise SpeechKitError(
            "Нет доступа к Yandex SpeechKit (tts.api.cloud.yandex.net). "
            "Проверь интернет/VPN/firewall."
        ) from exc
    except httpx.TimeoutException as exc:
        raise SpeechKitError(f"SpeechKit TTS timeout: {exc}") from exc
    except httpx.HTTPError as exc:
        raise SpeechKitError(f"SpeechKit TTS network error: {type(exc).__name__}: {exc}") from exc

    if response.status_code >= 400:
        logger.error("SpeechKit TTS error %s: %s", response.status_code, response.text)
        raise SpeechKitError(f"SpeechKit TTS failed: {response.status_code} {response.text}")

    return response.content
