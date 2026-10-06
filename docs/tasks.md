# AI Call Agent — Track 1

> Ветка бэка: `feature/backend` (только `backend/` + `tests/`). В `main`: ещё и `frontend/`. Фронт с бэка не трогаем.

## Вердикт по ТЗ (трек 1)

**Обязательные требования трека 1 для хакатон-прототипа — закрываем на бэке.**  
Полный «операторский прод» из лекций (SIP-биллинг, юр. шифрование PDn, Realtime-труба) — **нет**, это narrative на защите, не код.

| ТЗ (обязательное) | Бэк | Как закрыто |
|---|---|---|
| Простота ≤ 5 мин | да | локальный контур + README /health |
| Маршрутизация голос / Telegram-чат / человек | да | `action_required` + `routing_rules` |
| Точность расшифровки / суть | да | Whisper + `summary` |
| Контроль: история + сценарии + правила | да | SQLite + `/scenarios` + `/routing_rules` |
| Конфиденциальность (демо) | да | всё локально, без облака на демо |
| CJM: уведомление Ивану | да | `data/notifications.jsonl` + опц. Telegram |
| Усиление: аналитика | да | `GET /stats` |
| Усиление: горячая линия | да | `POST /hotline` + правило |

## Сделано (к CP1)

- [x] Локальный LLM: Ollama `qwen2.5:3b` + системный промпт Ивана (`LLM_PROVIDER=local`)
- [x] Локальный STT: faster-whisper `tiny` (`STT_PROVIDER=local`)
- [x] Локальный TTS: pyttsx3 / Windows SAPI (`TTS_PROVIDER=local`)
- [x] Structured JSON + fallback + disclosure + hard-routing guard + JSON-правила
- [x] История звонков SQLite + API
- [x] Сценарии `/scenarios`, правила `/routing_rules`, аналитика `/stats`, hotline `/hotline`
- [x] Notify Ивану (jsonl + опц. Telegram bot)
- [x] `process_call` / `process_call_voice` / `transcribe` / `synthesize`
- [x] Smoke: `tests/smoke_*.py` + `smoke_hard_routing.py`
- [x] Yandex опционально — на демо жюри не используем

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
5. Smoke без Ollama: `python tests/run_offline_suite.py`
6. Smoke LLM (когда Ollama готова): `python tests/smoke_hard_routing.py`

Опционально в `.env`:
```
LLM_PROVIDER=local
STT_PROVIDER=local
TTS_PROVIDER=local
OLLAMA_MODEL=qwen2.5:3b
WHISPER_MODEL_SIZE=tiny
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## API для закрытия ТЗ (без Ollama)

- `GET /api/v1/stats` — аналитика
- `GET|PUT|DELETE /api/v1/routing_rules` — правила маршрутизации
- `GET|PUT|DELETE /api/v1/scenarios` — приветствие / FAQ
- `POST /api/v1/hotline` — экстренный перевод на человека
- `GET /api/v1/calls?critical_only=true` — история важных

## Дальше

1. Прогон на живом Ollama + демо для жюри  
2. Стыковка с фронтом (UI сценариев / истории)  
3. При наличии GPU — `OLLAMA_MODEL=qwen2.5:7b`  
