"""Smoke: TTS → STT → process_call_voice (без микрофона)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.speechkit_stt import synthesize_ogg, transcribe_audio


PHRASE = "Соедините с менеджером, срочно по договору"


async def _prepare_ogg() -> bytes:
    print(f"TTS synthesize: {PHRASE!r}")
    audio = await synthesize_ogg(PHRASE)
    print(f"TTS ok bytes={len(audio)}")
    text = await transcribe_audio(audio, audio_format="oggopus")
    print(f"STT transcript: {text!r}")
    return audio


def main() -> None:
    audio = asyncio.run(_prepare_ogg())
    client = TestClient(app)
    files = {"audio": ("sample.ogg", audio, "audio/ogg")}
    data = {
        "session_id": "smoke-voice-1",
        "client_phone": "+79001112233",
        "audio_format": "oggopus",
        "lang": "ru-RU",
    }
    resp = client.post("/api/v1/process_call_voice", files=files, data=data)
    print("status", resp.status_code)
    body = resp.json()
    if resp.status_code != 200:
        print(body)
        raise SystemExit(1)
    print(
        f"call_id={body.get('call_id')} transcript={body.get('transcript')!r} "
        f"critical={body.get('is_critical')} intent={body.get('intent')} "
        f"action={body.get('action_required')}"
    )
    print("summary:", body.get("summary"))
    print("OK voice pipeline")


if __name__ == "__main__":
    main()
