# AI Call Agent — Track 1 (`feature/backend`)

> **main не трогаем.** Работа в ветке `feature/backend`, код в `backend/`.

## Статус

- [x] Чекпоинт 1: YandexGPT + системный промпт + `POST /api/v1/process_call`
- [x] История звонков (SQLite) — ТЗ «контроль и управление»
- [x] `frontend/` убран из этой ветки (остаётся в `main` / `feature/frontend`)

## ТЗ → БД

| Требование ТЗ | Как закрыто |
|---|---|
| Контроль: история звонков | таблица `call_logs` + `GET /api/v1/calls` |
| Суть обращения | поле `summary` + `user_message` (реплика/транскрипт) |
| Важное vs рутина | `is_critical`, фильтр `?critical_only=true` |
| Карточка для Ивана | `GET /api/v1/calls/{id}`: резюме, ответ агента, intent, action |
| Безопасность (прототип) | `data/calls.db` локально, в `.gitignore`, без API-ключей в БД |

## API

- `POST /api/v1/process_call` → ответ ИИ + `call_id` (запись в БД)
- `GET /api/v1/calls` / `?critical_only=true`
- `GET /api/v1/calls/{id}`
- `GET /health`

Запуск: `uvicorn backend.main:app --reload --port 8000`

```bash
python backend/scripts/smoke_test.py
python backend/scripts/smoke_history.py
```

## Дальше

- Telegram-уведомления
- SpeechKit
- Сценарии / правила (UI)
