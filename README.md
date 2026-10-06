# MTS Hackathon × Space — Track 1 (checkpoint 1)

ИИ-агент входящих звонков для IT-предпринимателя **Ивана Петрова**.

Стек: **Python + FastAPI + YandexGPT (AI Studio)** в папке `backend/`.

## API

`POST /api/v1/process_call` — реплика звонящего → JSON ответа ИИ.

| Поле | Смысл по ТЗ |
|------|-------------|
| `agent_response` | Что говорит агент звонящему |
| `is_critical` / `priority` | Важное обращение или рутина |
| `intent` | Категория (коммерция, жалоба, спам, эскалация…) |
| `action_required` | `continue_dialog` / `transfer_to_human` / `offer_telegram_chat` / `callback_recommended` |
| `summary` | Краткое резюме для Telegram Ивану |

`GET /health` — статус и флаг `yandex_configured`.

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# заполнить YC_FOLDER_ID и YC_API_KEY

uvicorn backend.main:app --reload --port 8000
```

Swagger: http://127.0.0.1:8000/docs

```bash
python scripts/smoke_test.py
```

## Структура

```
backend/                  # весь бэкенд Трека 1 (чекпоинт 1)
  main.py
  config.py
  schemas.py
  api/routes_call.py
  prompts/system_ivan.py
  services/yandex_llm.py
scripts/smoke_test.py
.env.example
```

## Коммиты

`feat:` / `fix:` / `docs:` / `chore:` / `refactor:`
