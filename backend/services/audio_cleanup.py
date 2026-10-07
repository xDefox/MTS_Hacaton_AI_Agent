"""Подготовка голосовых из шумной обстановки (поезд, улица) перед SpeechKit.

Декодируем в 16 кГц моно, срезаем низкочастотный гул, выравниваем громкость
и отдаём LPCM — SpeechKit v1 принимает его как format=lpcm.
"""

from __future__ import annotations

import io
import logging

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# SpeechKit sync STT: ≤ 30 с и ≤ 1 МБ (16 кГц × 16 бит = 32 КБ/с)
MAX_SECONDS = 29.5
HIGHPASS_HZ = 110.0
TARGET_RMS = 0.1
PEAK_LIMIT = 0.95


def _highpass(samples: np.ndarray, cutoff_hz: float) -> np.ndarray:
    spectrum = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(samples.size, d=1.0 / SAMPLE_RATE)
    # плавный скат вместо ступеньки, чтобы не было звона
    ramp = np.clip((freqs - cutoff_hz * 0.5) / (cutoff_hz * 0.5), 0.0, 1.0)
    return np.fft.irfft(spectrum * ramp, n=samples.size).astype(np.float32)


def _normalize(samples: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0
    if rms < 1e-5:
        return samples
    out = samples * (TARGET_RMS / rms)
    peak = float(np.max(np.abs(out)))
    if peak > PEAK_LIMIT:
        out = out * (PEAK_LIMIT / peak)
    return out


def clean_for_stt(audio: bytes) -> bytes | None:
    """Возвращает LPCM 16 кГц int16 или None, если декодировать не удалось."""
    if not audio:
        return None
    try:
        from faster_whisper.audio import decode_audio

        samples = decode_audio(io.BytesIO(audio), sampling_rate=SAMPLE_RATE)
    except Exception as exc:  # noqa: BLE001 — неизвестный контейнер: отправим исходник
        logger.info("Audio cleanup skipped (decode failed): %s", exc)
        return None
    if samples.size == 0:
        return None

    samples = samples[: int(MAX_SECONDS * SAMPLE_RATE)].astype(np.float32)
    samples = _highpass(samples, HIGHPASS_HZ)
    samples = _normalize(samples)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    logger.info(
        "Audio cleanup ok: %.1fs, %d -> %d bytes",
        samples.size / SAMPLE_RATE,
        len(audio),
        len(pcm),
    )
    return pcm
