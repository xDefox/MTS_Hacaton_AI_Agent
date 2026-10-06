# AI Call Agent — Track 1

> В `main`: `backend/` + `frontend/` + `tests/`. Бэк: YandexGPT, SpeechKit STT/TTS, SQLite, Telegram-уведомления. Фронт: Flet-онбординг + aiogram-бот Ивана.

## Сделано

### Бэкенд

- [x] YandexGPT + системный промпт Ивана + `POST /api/v1/process_call`
- [x] Structured JSON: `agent_response`, `is_critical`, `priority`, `intent`, `action_required`, `summary`
- [x] Fallback, если Yandex недоступен
- [x] История звонков (SQLite `data/calls.db`) — ТЗ «контроль и управление»
- [x] `GET /api/v1/calls`, `?critical_only=true`, `GET /api/v1/calls/{id}`
- [x] Сохранение после `process_call` / `process_call_voice` → `call_id`
- [x] SpeechKit STT: `POST /api/v1/transcribe`, голос→агент `POST /api/v1/process_call_voice`
- [x] SpeechKit TTS: `POST /synthesize`, `process_call?with_audio=true`, озвучка → `data/tts/`
- [x] `GET /api/v1/calls/{id}/audio` — скачать ответ агента голосом (демо)
- [x] Telegram: после реального `process_call` / `process_call_voice` бэкенд шлёт Ивану короткий отчёт (номер, резюме, ответ агента)
- [x] `POST /api/v1/telegram/subscribe` — регистрация `chat_id` после `/start` в боте
- [x] Smoke: `tests/smoke_*.py` (test / history / voice / tts)

### Фронтенд (Flet)

- [x] Заглушка входа в приложение МТС: номер спрашивается один раз при запуске (без повторной авторизации на подключении)
- [x] Каталог услуг (вторая карточка-заглушка) + выход из услуги обратно в каталог
- [x] Карточка подключения услуги «AI менеджер звонков»
- [x] Оферта + согласие; без галочки «Подключить» не срабатывает
- [x] После подключения — настройки чекбоксами (маршрутизация, история, сценарии, горячая линия)
- [x] Кнопка «Перейти в Telegram-бота» только после подключения (`TG_BOT_URL`)
- [x] Тесты UI: `python -m tests.test_service_page`

### Telegram-бот

- [x] `/start` — одно сообщение «Услуга подключена», бот **не** генерирует звонок сам
- [x] Регистрация чата Ивана (`data/tg_chats.txt` + `TG_CHAT_ID`)
- [x] Отчёт приходит с бэкенда, когда второй человек бьёт в `process_call` / `process_call_voice`
- [x] Токен только из `.env` (`TG_BOT_TOKEN`), не в коде

## ТЗ → продукт

| Требование ТЗ / CJM | Статус |
|---|---|
| ИИ принимает входящие за Ивана | есть (текст и голос → агент) |
| Важное vs рутина | `is_critical`, фильтр `critical_only` |
| Точность расшифровки / суть | SpeechKit STT + `summary` |
| Ответ голосом звонящему | SpeechKit TTS (демо-файл); в проде — стрим |
| Контроль: история звонков | SQLite + API |
| Маршрутизация голос / чат / человек | промпт + `action_required` + чекбоксы в Flet |
| Уведомление о записи разговора | в системном промпте |
| Безопасность прототипа | локальная БД, `.gitignore`, ключи в `.env` |
| Онбординг ≤ 5 мин / UI сценариев | Flet: карточка → согласие → настройки |
| Telegram-уведомление Ивану | `/start` + отчёт с бэкенда после ручки |
| SpeechKit Realtime | дальше (сейчас sync STT/TTS) |

## Безопасность БД (хакатон)

OK для демо: локальный файл, не в git, без ключей в таблице.  
В презентации: прод = контур МТС, Postgres, auth, шифрование, аудит доступа.

## API / запуск

```bash
.\.venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
# Swagger: http://127.0.0.1:8000/docs

python -m frontend.app
python -m frontend.tg_bot
# сначала /start у бота, затем звонок в API

python tests/smoke_test.py
python tests/smoke_history.py
python tests/smoke_voice.py
python tests/smoke_tts.py
python -m tests.test_service_page
```

`.env`: `YC_FOLDER_ID`, `YC_API_KEY`, `TG_BOT_TOKEN`. Опционально `TG_CHAT_ID`, `TG_BOT_URL`.  
Демо TTS: `data/tts/` (не в git). Подписчики бота: `data/tg_chats.txt` (не в git).

## Дальше

1. SpeechKit Realtime / стрим TTS в телефонию  
2. Дашборд истории в Flet (`GET /calls`)  
3. Прод-контур: Postgres, auth, без долгого хранения аудио  
