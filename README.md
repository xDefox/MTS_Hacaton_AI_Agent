# MTS Hackathon × Space — Track 1

ИИ-агент входящих звонков для IT-предпринимателя **Ивана Петрова**.

Стек: **Python + FastAPI + YandexGPT (AI Studio) + SQLite** + системный промпт по CJM/ТЗ.

## Что умеет сейчас

`POST /api/v1/process_call` — реплика звонящего → ответ ИИ + сохранение в историю.

| Поле | Смысл по ТЗ |
|------|-------------|
| `agent_response` | Что говорит агент звонящему |
| `is_critical` / `priority` | Важное обращение или рутина |
| `intent` | Категория (коммерция, жалоба, спам, эскалация…) |
| `action_required` | `continue_dialog` / `transfer_to_human` / `offer_telegram_chat` / `callback_recommended` |
| `summary` | Краткое резюме для Telegram Ивану |
| `call_id` | ID записи в локальной истории |

История (ТЗ: контроль и управление):

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

4. В `.env`: `YC_FOLDER_ID` и `YC_API_KEY`.
5. Запуск API:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

6. Swagger: http://127.0.0.1:8000/docs  
7. Health: http://127.0.0.1:8000/health  

### Smoke-тесты

```bash
python scripts/smoke_test.py
python scripts/smoke_history.py
```

## Данные и безопасность (прототип хакатона)

- История хранится **локально** в `data/calls.db` (SQLite). Файл в `.gitignore` — **не коммитить**.
- В БД нет API-ключей; только содержимое обращений (для демо).
- Уведомление звонящего о записи/обработке — в системном промпте.
- На хакатоне API без auth (localhost). В проде / контуре МТС: auth через ЛК, ПДн в национальном контуре, шифрование at rest, аудит доступа (right to review).
- Путь масштабирования: SQLite (пилот) → Postgres в контуре оператора.

## Структура

```
backend/
  main.py                 # FastAPI entry + init_db
  config.py               # env + DATABASE_URL
  database.py             # SQLAlchemy engine
  models.py               # CallLog ORM
  schemas.py              # API contracts
  api/routes_call.py      # process_call + history GETs
  prompts/system_ivan.py
  services/yandex_llm.py
  services/call_history.py
frontend/                 # Flet / Telegram (партнёр)
scripts/smoke_test.py
scripts/smoke_history.py
data/calls.db             # создаётся локально, не в git
```

## Коммиты

Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.

## Дальше по ТЗ

- Telegram-уведомление Ивану (резюме + расшифровка)
- SpeechKit STT/TTS
- UI: список истории уже можно кормить с `GET /calls`; сценарии / правила
