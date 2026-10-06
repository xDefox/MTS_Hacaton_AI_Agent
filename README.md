# MTS Hackathon × Space — Track 1

ИИ-агент входящих звонков для IT-предпринимателя **Ивана Петрова**.

Стек чекпоинта 1: **Python + FastAPI + YandexGPT (AI Studio)** + системный промпт по CJM/ТЗ.

## Что умеет сейчас

`POST /api/v1/process_call` принимает текст реплики звонящего (позже — STT) и возвращает:

| Поле | Смысл по ТЗ |
|------|-------------|
| `agent_response` | Что говорит агент звонящему |
| `is_critical` / `priority` | Важное обращение или рутина |
| `intent` | Категория (коммерция, жалоба, спам, эскалация…) |
| `action_required` | `continue_dialog` / `transfer_to_human` / `offer_telegram_chat` / `callback_recommended` |
| `summary` | Краткое резюме для Telegram Ивану |

## Быстрый старт (≤ 5 минут)

1. Python 3.10+
2. Создайте каталог в [Yandex Cloud](https://console.yandex.cloud/), включите **AI Studio / Foundation Models**, получите API-ключ.
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

### Smoke-тест трёх сценариев (лид / спам / «соедините с менеджером»)

```bash
python scripts/smoke_test.py
```

### Пример запроса

```bash
curl -X POST http://127.0.0.1:8000/api/v1/process_call ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"demo-1\",\"user_message\":\"Соедините с менеджером, срочно по договору\",\"client_phone\":\"+79001112233\"}"
```

## Структура

```
backend/
  main.py                 # FastAPI entry
  config.py               # env settings
  schemas.py              # request/response contracts
  api/routes_call.py      # POST /api/v1/process_call
  prompts/system_ivan.py  # system prompt (Трек 1)
  services/yandex_llm.py  # YandexGPT + JSON parse + fallback
frontend/                 # Flet / Telegram (партнёр)
scripts/smoke_test.py
```

## Коммиты

Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.

## Дальше по ТЗ

- Telegram-уведомление Ивану (резюме + расшифровка)
- История звонков (SQLite)
- SpeechKit STT/TTS
- UI: сценарии / правила маршрутизации
