"""STT / TTS provider facade (local by default)."""

from __future__ import annotations

import asyncio
import logging

from backend.config import get_settings

logger = logging.getLogger(__name__)


class SpeechError(RuntimeError):
    """Unified speech error."""


async def transcribe_bytes(
    audio: bytes,
    *,
    lang: str = "ru-RU",
    audio_format: str = "oggopus",
    sample_rate_hertz: int | None = None,
    filename: str | None = None,
) -> tuple[str, str]:
    """Returns (transcript, engine_name)."""
    settings = get_settings()
    provider = (settings.stt_provider or "local").strip().lower()
    if provider == "yandex":
        from backend.services.speechkit_stt import SpeechKitError, transcribe_audio

        try:
            text = await transcribe_audio(
                audio,
                audio_format=audio_format,  # type: ignore[arg-type]
                lang=lang,
                sample_rate_hertz=sample_rate_hertz,
            )
        except SpeechKitError as exc:
            raise SpeechError(str(exc)) from exc
        return text, "yandex-speechkit"

    from backend.services.local_stt import LocalSTTError, transcribe_audio_local

    language = "ru" if lang.lower().startswith("ru") else lang.split("-")[0]
    try:
        text = await asyncio.to_thread(
            transcribe_audio_local,
            audio,
            language=language,
            filename=filename,
        )
    except LocalSTTError as exc:
        raise SpeechError(str(exc)) from exc
    return text, f"faster-whisper:{settings.whisper_model_size}"


async def synthesize_agent_audio(text: str) -> tuple[bytes, str, str]:
    """Returns (audio_bytes, ext ogg|wav, engine_name)."""
    settings = get_settings()
    provider = (settings.tts_provider or "local").strip().lower()
    if provider == "yandex":
        from backend.services.speechkit_stt import SpeechKitError, synthesize_ogg

        try:
            audio = await synthesize_ogg(
                text, voice=settings.tts_voice, lang=settings.tts_lang
            )
        except SpeechKitError as exc:
            raise SpeechError(str(exc)) from exc
        return audio, "ogg", "yandex-speechkit"

    from backend.services.local_tts import LocalTTSError, synthesize_wav_local

    timeout = max(5.0, float(get_settings().tts_timeout_sec))
    try:
        audio = await asyncio.wait_for(
            asyncio.to_thread(synthesize_wav_local, text),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        raise SpeechError(f"Local TTS timeout after {timeout:.0f}s") from exc
    except LocalTTSError as exc:
        raise SpeechError(str(exc)) from exc
    return audio, "wav", "pyttsx3-local"
