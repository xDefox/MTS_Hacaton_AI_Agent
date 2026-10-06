# AI Call Agent — Track 1 (`feature/backend`)

> **main не мержим пока.** Вся работа бэка в папке `backend/`.

## Статус

- [x] Чекпоинт 1: YandexGPT + системный промпт + `POST /api/v1/process_call`
- [x] История звонков (SQLite) — ТЗ «контроль и управление»
- [x] Код бэкенда в папке `backend/` (для будущего разделения backend / frontend в main)
- [x] `frontend/` нет в этой ветке (остаётся в `main`)

## ТЗ → продукт

| Требование ТЗ | Статус |
|---|---|
| Контроль: история звонков | `call_logs` + `GET /api/v1/calls` |
| Суть обращения | `summary` + `user_message` |
| Важное vs рутина | `is_critical`, `?critical_only=true` |
| Карточка для Ивана | `GET /api/v1/calls/{id}` |
| Маршрутизация голос/чат/человек | в промпте + `action_required` |
| Безопасность (прототип) | локальный `data/calls.db`, `.gitignore`, ключи только в `.env` |
| Онбординг ≤ 5 мин / UI сценариев | ещё нет (фронт) |
| Telegram-уведомление | ещё нет |

## API

Запуск: `uvicorn backend.main:app --reload --port 8000`

```bash
python scripts/smoke_test.py
python scripts/smoke_history.py
```
