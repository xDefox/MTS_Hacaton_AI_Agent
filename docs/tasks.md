# AI Call Agent — Track 1

> Бэкенд: `feature/backend`. В `main`: `backend/` + `frontend/` + `tests/` (smoke бэка и тесты фронта). Фронт и `test_service_page.py` с бэка не трогаем.

## Сделано (к CP1)

- [x] YandexGPT + системный промпт Ивана + `POST /api/v1/process_call`
- [x] Structured JSON: `agent_response`, `is_critical`, `priority`, `intent`, `action_required`, `summary`
- [x] Fallback, если Yandex недоступен
- [x] История звонков (SQLite `data/calls.db`) — ТЗ «контроль и управление»
- [x] `GET /api/v1/calls`, `?critical_only=true`, `GET /api/v1/calls/{id}`
- [x] Сохранение после `process_call` / `process_call_voice` → `call_id`
- [x] SpeechKit STT: `POST /api/v1/transcribe`, голос→агент `POST /api/v1/process_call_voice`
- [x] SpeechKit TTS: `POST /synthesize`, `process_call?with_audio=true`, озвучка → `data/tts/`
- [x] `GET /api/v1/calls/{id}/audio` — скачать ответ агента голосом (демо)
- [x] Smoke: `tests/smoke_*.py` (test / history / voice / tts)
- [x] Предупреждение «вы общаетесь с ИИ» + запись — всегда перед `agent_response` (текст и TTS)
- [x] Структура: в `main` — `backend/` + `frontend/`; наши smoke в `tests/` рядом с тестами фронта

## ТЗ → продукт

| Требование ТЗ / CJM | Статус |
|---|---|
| ИИ принимает входящие за Ивана | есть (текст и голос → агент) |
| Важное vs рутина | `is_critical`, фильтр `critical_only` |
| Точность расшифровки / суть | SpeechKit STT + `summary` |
| Ответ голосом звонящему | SpeechKit TTS (демо-файл); в проде — стрим |
| Контроль: история звонков | SQLite + API |
| Маршрутизация голос / чат / человек | промпт + `action_required` |
| Уведомление о записи разговора | всегда префикс перед `agent_response` (текст + голос) |
| Безопасность прототипа | локальная БД, `.gitignore`, ключи в `.env` |
| Онбординг ≤ 5 мин / UI сценариев | фронт (партнёр) |
| Telegram-уведомление Ивану | есть на `main` (`telegram_notify`) |
| SpeechKit Realtime | дальше (сейчас sync STT/TTS) |

## Безопасность БД (хакатон)

OK для демо: локальный файл, не в git, без ключей в таблице.  
В презентации: прод = контур МТС, Postgres, auth, шифрование, аудит доступа.

## API / запуск

```bash
.\.venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
# Swagger: http://127.0.0.1:8000/docs  (API 1.3.0+)

python tests/smoke_test.py
python tests/smoke_history.py
python tests/smoke_voice.py
python tests/smoke_tts.py
```

Демо: короткий `.ogg` в `process_call_voice`; озвучка ответа — `with_audio=true` → `audio_url` / `GET /calls/{id}/audio`.  
Файлы в `data/tts/` локально (не в git). По ТЗ в проде — стрим в трубку, без долгого хранения.

## Дальше

1. Telegram-уведомление Ивану (`summary` + transcript)  
2. Стыковка с фронтом (`GET /calls`)  
3. SpeechKit Realtime / стрим TTS в телефонию  
