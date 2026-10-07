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


def _level_speech(samples: np.ndarray) -> np.ndarray:
    """Выравнивание громкости по ходу фразы (отодвинул телефон, говорит тише).

    Тихие участки речи подтягиваются до +12 дБ, громкие слегка прижимаются.
    Паузы получают минимальное усиление из речевых участков — шум не раздувается.
    """
    frame = SAMPLE_RATE // 20  # 50 мс
    n = samples.size // frame
    if n < 10:
        return samples
    frames = samples[: n * frame].reshape(n, frame)
    rms = np.sqrt(np.mean(frames**2, axis=1)) + 1e-8
    floor = float(np.percentile(rms, 20))
    speech = rms > max(floor * 2.5, 1e-4)
    if speech.sum() < 3:
        return samples
    target = float(np.median(rms[speech]))
    gain = np.clip(target / rms, 0.7, 4.0)
    gain[~speech] = float(gain[speech].min())
    gain = np.convolve(gain, np.ones(5) / 5, mode="same")  # без резких скачков
    per_sample = np.interp(
        np.arange(samples.size), (np.arange(n) + 0.5) * frame, gain
    ).astype(np.float32)
    return samples * per_sample


def _normalize(samples: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0
    if rms < 1e-5:
        return samples
    out = samples * (TARGET_RMS / rms)
    peak = float(np.max(np.abs(out)))
    if peak > PEAK_LIMIT:
        out = out * (PEAK_LIMIT / peak)
    return out


def _as_frames(result) -> list:
    if result is None:
        return []
    return result if isinstance(result, list) else [result]


def _decode(audio: bytes) -> np.ndarray:
    """Любой контейнер (ogg/opus, wav, mp3, m4a) → float32 моно 16 кГц.

    Через av напрямую: faster_whisper.decode_audio передаёт аргументы,
    которых нет в части версий av.
    """
    import av

    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks: list[np.ndarray] = []
    with av.open(io.BytesIO(audio), mode="r") as container:
        stream = container.streams.audio[0]
        for frame in container.decode(stream):
            frame.pts = None
            for out in _as_frames(resampler.resample(frame)):
                chunks.append(out.to_ndarray().reshape(-1))
        try:
            for out in _as_frames(resampler.resample(None)):
                chunks.append(out.to_ndarray().reshape(-1))
        except Exception:  # noqa: BLE001 — старые av не умеют flush
            pass
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def clean_for_stt(audio: bytes) -> bytes | None:
    """Возвращает LPCM 16 кГц int16 или None, если декодировать не удалось."""
    if not audio:
        return None
    try:
        samples = _decode(audio)
    except Exception as exc:  # noqa: BLE001 — неизвестный контейнер: отправим исходник
        logger.info("Audio cleanup skipped (decode failed): %s", exc)
        return None
    if samples.size == 0:
        return None

    samples = samples[: int(MAX_SECONDS * SAMPLE_RATE)].astype(np.float32)
    samples = _highpass(samples, HIGHPASS_HZ)
    samples = _level_speech(samples)
    samples = _normalize(samples)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    logger.info(
        "Audio cleanup ok: %.1fs, %d -> %d bytes",
        samples.size / SAMPLE_RATE,
        len(audio),
        len(pcm),
    )
    return pcm
