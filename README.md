# MTS Hackathon × Space — Track 1

ИИ-агент входящих звонков для IT-предпринимателя **Ивана Петрова**.

Стек: **Python + FastAPI + YandexGPT + SpeechKit STT + SQLite** + системный промпт по CJM/ТЗ.  
Фронт: **Flet / Telegram** в `frontend/` (партнёр).

## Что умеет сейчас

`POST /api/v1/process_call` — текст реплики → ответ ИИ + запись в историю.  
`POST /api/v1/process_call_voice` — аудио (SpeechKit STT) → тот же агент + история.  
`POST /api/v1/transcribe` — только голос → текст.

| Поле | Смысл по ТЗ |
|------|-------------|
| `transcript` | Распознанная речь (только voice-эндпоинты) |
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
```

4. Создайте `.env` в корне (файл не в git) и укажите `YC_FOLDER_ID` и `YC_API_KEY`.
5. Запуск API:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

6. Swagger: http://127.0.0.1:8000/docs  
7. Health: http://127.0.0.1:8000/health  

### Frontend (Flet)

Код партнёра в `frontend/`. Запуск UI:

```bash
python frontend/app.py
```

### Smoke-тесты

```bash
python tests/smoke_test.py
python tests/smoke_history.py
python tests/smoke_voice.py
```

### Голос (SpeechKit)

- `POST /api/v1/transcribe` — аудио → текст  
- `POST /api/v1/process_call_voice` — аудио → STT → агент → история  

В Swagger загружайте **короткий** `.ogg` (OggOpus, до ~1 МБ / одна фраза).  
Длинные песни sync STT не принимает. Без микрофона: `python tests/smoke_voice.py`.

### Пример запроса

```bash
curl -X POST http://127.0.0.1:8000/api/v1/process_call ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"demo-1\",\"user_message\":\"Соедините с менеджером, срочно по договору\",\"client_phone\":\"+79001112233\"}"
```

## Структура

```
backend/                  # бэкенд Трека 1
  main.py
  config.py
  database.py             # SQLite
  models.py               # CallLog
  schemas.py
  api/routes_call.py
  prompts/system_ivan.py
  services/yandex_llm.py
  services/call_history.py
  services/speechkit_stt.py  # STT (+ TTS для smoke)
frontend/                 # Flet / Telegram (партнёр)
data/calls.db             # локально, не в git
docs/                     # ТЗ, CJM, tasks.md
tests/                    # smoke бэка + тесты фронта
  smoke_test.py
  smoke_history.py
  smoke_voice.py
  test_service_page.py
```

## Данные и безопасность (прототип)

- История в `data/calls.db` (SQLite), папка в `.gitignore`.
- API-ключи только в `.env`, не в БД.
- Для продакшена / презентации жюри: контур МТС, Postgres, auth, шифрование, аудит доступа.

## Коммиты

Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.

## Дальше по ТЗ

- Telegram-уведомление Ивану (резюме + расшифровка)
- SpeechKit Realtime / ответ агента голосом (TTS в телефонию)
- UI: дашборд истории, сценарии / правила маршрутизации
