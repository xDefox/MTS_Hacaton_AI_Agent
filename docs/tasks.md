# AI Call Agent — Track 1

> Ветка бэка: `feature/backend` (только `backend/`). В `main`: `backend/` + `frontend/`. Без `.env.example` в репозитории.

## Сделано

- [x] Чекпоинт 1: YandexGPT + системный промпт Ивана + `POST /api/v1/process_call`
- [x] Structured JSON: `agent_response`, `is_critical`, `priority`, `intent`, `action_required`, `summary`
- [x] Fallback, если Yandex недоступен
- [x] История звонков (SQLite `data/calls.db`) — ТЗ «контроль и управление»
- [x] `GET /api/v1/calls`, `?critical_only=true`, `GET /api/v1/calls/{id}`
- [x] Сохранение после каждого `process_call` → `call_id`
- [x] Smoke-тесты: `backend/scripts/smoke_*.py`
- [x] Структура: бэк в `backend/` (фронт только в `main`)

## ТЗ → продукт

| Требование ТЗ / CJM | Статус |
|---|---|
| ИИ принимает входящие за Ивана | есть (текст → агент) |
| Суть обращения / резюме | `summary` + `user_message` |
| Важное vs рутина | `is_critical`, фильтр `critical_only` |
| Контроль: история звонков | SQLite + API |
| Маршрутизация голос / чат / человек | промпт + `action_required` |
| Уведомление о записи разговора | в системном промпте |
| Безопасность прототипа | локальная БД, `.gitignore`, ключи в `.env` |
| Онбординг ≤ 5 мин / UI сценариев | ещё нет (фронт) |
| Telegram-уведомление Ивану | ещё нет |
| SpeechKit голос | ещё нет |

## Безопасность БД (хакатон)

OK для демо: локальный файл, не в git, без ключей в таблице.  
В презентации: прод = контур МТС, Postgres, auth, шифрование, аудит доступа.

## API / запуск

```bash
.\.venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
# Swagger: http://127.0.0.1:8000/docs

python backend/scripts/smoke_test.py
python backend/scripts/smoke_history.py
```

## Дальше

1. Telegram-уведомление после звонка  
2. Стыковка с фронтом (`GET /calls`)  
3. SpeechKit / сценарии UI  
