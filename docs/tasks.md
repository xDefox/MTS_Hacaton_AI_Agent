# AI Call Agent — Track 1

> Бэкенд развивается в `feature/backend`. В `main`: `backend/` + `frontend/` (фронт не трогаем с бэка).

## Сделано (к CP1)

- [x] YandexGPT + системный промпт Ивана + `POST /api/v1/process_call`
- [x] Structured JSON: `agent_response`, `is_critical`, `priority`, `intent`, `action_required`, `summary`
- [x] Fallback, если Yandex недоступен
- [x] История звонков (SQLite `data/calls.db`) — ТЗ «контроль и управление»
- [x] `GET /api/v1/calls`, `?critical_only=true`, `GET /api/v1/calls/{id}`
- [x] Сохранение после `process_call` / `process_call_voice` → `call_id`
- [x] SpeechKit STT: `POST /api/v1/transcribe`, голос→агент `POST /api/v1/process_call_voice`
- [x] Smoke: `smoke_test.py`, `smoke_history.py`, `smoke_voice.py`
- [x] Структура: бэк в `backend/` (фронт только в `main`)

## ТЗ → продукт

| Требование ТЗ / CJM | Статус |
|---|---|
| ИИ принимает входящие за Ивана | есть (текст и голос → агент) |
| Важное vs рутина | `is_critical`, фильтр `critical_only` |
| Точность расшифровки / суть | SpeechKit STT + `summary` |
| Контроль: история звонков | SQLite + API |
| Маршрутизация голос / чат / человек | промпт + `action_required` |
| Уведомление о записи разговора | в системном промпте |
| Безопасность прототипа | локальная БД, `.gitignore`, ключи в `.env` |
| Онбординг ≤ 5 мин / UI сценариев | ещё нет (фронт) |
| Telegram-уведомление Ивану | ещё нет |
| SpeechKit Realtime / ответ голосом | STT sync есть; Realtime/TTS в трубку — дальше |

## Безопасность БД (хакатон)

OK для демо: локальный файл, не в git, без ключей в таблице.  
В презентации: прод = контур МТС, Postgres, auth, шифрование, аудит доступа.

## API / запуск

```bash
.\.venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
# Swagger: http://127.0.0.1:8000/docs  (версия API 1.2.0+)

python backend/scripts/smoke_test.py
python backend/scripts/smoke_history.py
python backend/scripts/smoke_voice.py
```

Демо голоса в Swagger: короткий `.ogg` (до ~1 МБ), например `data/demo_call.ogg`. Не загружать длинные песни.

## Дальше

1. Telegram-уведомление Ивану (`summary` + transcript)  
2. Стыковка с фронтом (`GET /calls`)  
3. SpeechKit Realtime / TTS-ответ звонящему  
