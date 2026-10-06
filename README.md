# MTS Hackathon × Space — Track 1

ИИ-агент входящих звонков для IT-предпринимателя **Ивана Петрова**.

Стек: **Python + FastAPI + YandexGPT (AI Studio) + SQLite** + системный промпт по CJM/ТЗ.

## Что умеет сейчас

`POST /api/v1/process_call` — реплика звонящего → ответ ИИ + запись в историю.

| Поле | Смысл по ТЗ |
|------|-------------|
| `agent_response` | Что говорит агент звонящему |
| `is_critical` / `priority` | Важное обращение или рутина |
| `intent` | Категория (коммерция, жалоба, спам, эскалация…) |
| `action_required` | `continue_dialog` / `transfer_to_human` / `offer_telegram_chat` / `callback_recommended` |
| `summary` | Краткое резюме для Telegram Ивану |
| `call_id` | ID записи в локальной истории |

История звонков (ТЗ: контроль и управление):

- `GET /api/v1/calls` — список (новые сверху)
- `GET /api/v1/calls?critical_only=true` — только важные
- `GET /api/v1/calls/{id}` — детали карточки

## Быстрый старт (≤ 5 минут)

1. Python 3.10+
2. Каталог в [Yandex Cloud](https://console.yandex.cloud/), AI Studio / Foundation Models, API-ключ.
3. Установка:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

4. В `.env` укажите `YC_FOLDER_ID` и `YC_API_KEY`.
5. Запуск API:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

6. Swagger: http://127.0.0.1:8000/docs  
7. Health: http://127.0.0.1:8000/health  

### Smoke-тесты

```bash
python backend/scripts/smoke_test.py
python backend/scripts/smoke_history.py
```

### Пример запроса

```bash
curl -X POST http://127.0.0.1:8000/api/v1/process_call ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"demo-1\",\"user_message\":\"Соедините с менеджером, срочно по договору\",\"client_phone\":\"+79001112233\"}"
```

## Структура

```
backend/                  # весь бэкенд Трека 1
  main.py
  config.py
  database.py             # SQLite
  models.py               # CallLog
  schemas.py
  api/routes_call.py
  prompts/system_ivan.py
  services/yandex_llm.py
  services/call_history.py
  scripts/smoke_test.py
  scripts/smoke_history.py
frontend/                 # Flet / Telegram (партнёр)
data/calls.db             # локально, не в git
docs/                     # ТЗ, CJM, tasks.md
```

## Данные и безопасность (прототип)

- История в `data/calls.db` (SQLite), папка в `.gitignore`.
- API-ключи только в `.env`, не в БД.
- Для продакшена / презентации жюри: контур МТС, Postgres, auth, шифрование, аудит доступа.

## Коммиты

Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.

## Дальше по ТЗ

- Telegram-уведомление Ивану (резюме + расшифровка)
- SpeechKit STT/TTS
- UI: дашборд истории, сценарии / правила маршрутизации
