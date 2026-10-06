"""Smoke: process_call?with_audio=true → TTS файл в data/tts/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.tts_storage import audio_path_for_call


def main() -> None:
    client = TestClient(app)
    payload = {
        "session_id": "smoke-tts-1",
        "client_phone": "+79001112233",
        "user_message": "Соедините с менеджером, срочно по договору",
    }
    resp = client.post("/api/v1/process_call", params={"with_audio": True}, json=payload)
    print("status", resp.status_code)
    body = resp.json()
    if resp.status_code != 200:
        print(body)
        raise SystemExit(1)

    call_id = body.get("call_id")
    audio_url = body.get("audio_url")
    print(f"call_id={call_id} audio_url={audio_url}")
    print(f"agent_response={body.get('agent_response')!r}")

    assert call_id, "call_id missing"
    assert audio_url, "audio_url missing — TTS failed?"
    path = audio_path_for_call(call_id)
    assert path.is_file() and path.stat().st_size > 0, f"missing file {path}"

    audio = client.get(audio_url)
    print("audio GET", audio.status_code, "bytes", len(audio.content))
    assert audio.status_code == 200
    assert len(audio.content) > 100
    print("OK tts pipeline")


if __name__ == "__main__":
    main()
