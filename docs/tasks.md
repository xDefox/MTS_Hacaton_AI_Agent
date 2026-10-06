# AI Call Agent — Track 1

> Ветка бэка: `feature/backend` (только `backend/` + `tests/`). В `main`: ещё и `frontend/`. Фронт с бэка не трогаем.

## Сделано (к CP1)

- [x] Локальный LLM: Ollama `qwen2.5:3b` + системный промпт Ивана (`LLM_PROVIDER=local`)
- [x] Локальный STT: faster-whisper `tiny` (`STT_PROVIDER=local`)
- [x] Локальный TTS: pyttsx3 / Windows SAPI (`TTS_PROVIDER=local`)
- [x] Structured JSON + fallback + disclosure + hard-routing guard
- [x] История звонков SQLite + API
- [x] `process_call` / `process_call_voice` / `transcribe` / `synthesize`
- [x] Smoke: `tests/smoke_*.py` + `smoke_hard_routing.py`
- [x] Yandex оставлен опционально (`llm_provider=yandex`) — на демо жюри не используем

## ТЗ → продукт

| Требование ТЗ / CJM | Статус |
|---|---|
| ИИ принимает входящие за Ивана | локальный LLM + Whisper |
| Важное vs рутина | `is_critical`, фильтр `critical_only` |
| Точность расшифровки / суть | Whisper STT + `summary` |
| Ответ голосом | локальный TTS → `data/tts/` |
| Контроль: история | SQLite + API |
| Маршрутизация голос / чат / человек | промпт + `action_required` + guard |
| Без внешних API на демо | Ollama + Whisper + pyttsx3 на localhost |
| Уведомление о записи | префикс перед `agent_response` |

## Локальный запуск (обязательно)

1. Установить [Ollama](https://ollama.com/download) для Windows.
2. В терминале:
```bash
ollama pull qwen2.5:3b
ollama serve
```
3. Backend:
```bash
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```
4. Проверка: `GET /health` → `llm_provider=local`, `ollama_model=qwen2.5:3b`
5. Smoke: `python tests/smoke_hard_routing.py`

Опционально в `.env`:
```
LLM_PROVIDER=local
STT_PROVIDER=local
TTS_PROVIDER=local
OLLAMA_MODEL=qwen2.5:3b
WHISPER_MODEL_SIZE=tiny
```

## Дальше

1. Прогон на живом Ollama + демо для жюри  
2. Стыковка с фронтом  
3. При наличии GPU — `OLLAMA_MODEL=qwen2.5:7b`  
