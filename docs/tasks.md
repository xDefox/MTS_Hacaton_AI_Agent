# AI Call Agent — Track 1 (checkpoint 1)

> Ветка: `feature/backend`. Код бэкенда: **`backend/`**.

**Статус чекпоинта 1:** ✅ YandexGPT + системный промпт Ивана + `POST /api/v1/process_call`.

## Трек

ИИ-секретарь принимает **входящие** звонки за Ивана Петрова → отвечает звонящему → отдаёт `summary` + `is_critical` для Ивана.

## Must-have ТЗ

- [ ] Подключение ≤ 5 мин (UI)
- [x] Маршрутизация в логике API/промпта (голос / чат / человек)
- [x] Суть обращения (`summary`)
- [ ] Контроль: история / сценарии (следующий этап)
- [~] Безопасность: фраза о записи в промпте

## API

- `POST /api/v1/process_call`
- `GET /health`

Запуск: `uvicorn backend.main:app --reload --port 8000`

## Дальше (не в main checkpoint 1)

- История звонков (SQLite)
- Telegram / Flet UI
- SpeechKit
