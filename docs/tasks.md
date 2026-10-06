# AI Call Agent — Track 1 (`feature/backend`)

> **main не трогаем.** Работа в ветке `feature/backend`, код в `app/`.

## Статус

- [x] Чекпоинт 1: YandexGPT + системный промпт + `POST /api/v1/process_call`
- [x] История звонков (SQLite) — ТЗ «контроль и управление»
- [x] Папка `backend/` убрана — пакет называется `app/`
- [x] `frontend/` убран из этой ветки (остаётся в `main`)

## ТЗ → БД

| Требование ТЗ | Как закрыто |
|---|---|
| Контроль: история звонков | таблица `call_logs` + `GET /api/v1/calls` |
| Суть обращения | поле `summary` + `user_message` |
| Важное vs рутина | `is_critical`, фильтр `?critical_only=true` |
| Карточка для Ивана | `GET /api/v1/calls/{id}` |
| Безопасность (прототип) | `data/calls.db` локально, в `.gitignore` |

## API

Запуск: `uvicorn app.main:app --reload --port 8000`

```bash
python scripts/smoke_test.py
python scripts/smoke_history.py
```
