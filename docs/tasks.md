# AI Call Agent — Track 1

> Ветка бэка: `feature/backend` (только `backend/` + `tests/`). В `main`: ещё и `frontend/`. Фронт с бэка не трогаем.

## Вердикт по ТЗ (трек 1)

**Обязательные требования трека 1 для хакатон-прототипа — закрываем на бэке.**  
Полный «операторский прод» из лекций (SIP-биллинг, юр. шифрование PDn, Realtime-труба) — **нет**, это narrative на защите, не код.

### Как читать ТЗ vs слова жюри/организаторов

| Источник | Что сказано | Как делаем |
|---|---|---|
| CJM + лекция · обязательное | ИИ понял суть; маршрутизация голос/чат; **настройка правил**; история; ≤5 мин; конфиденциальность | LLM (`ollama`) + `routing_rules` поверх ответа + SQLite/API |
| Лекция · оператор МТС | «Внешне» через каналы МТС; локальный контур данных; **не ухудшать QoS** (задержка на голосовом тракте) | На защите: narrative «встраиваемся в бот/ЛК МТС»; локальный Ollama (не зарубежное облако) |
| Лекция · прототип | Можно один cloud API на хакатоне, но показать путь в инфру оператора | Демо = local LLM; слайд = ЦОД/SIP/биллинг |
| Организаторы (устно) | **Строго LLM** на демо | `OLLAMA_RULES_FAST_PATH=false` (default): каждый `process_call` идёт в модель; правила только post-guard |
| Скорость | В ТЗ нет «SLA ответа LLM»; есть **простота ≤5 мин**, QoS линии (задержка пакетов), Иван **быстро** смотрит резюме | Warmup при старте; greeting TTS параллельно голосу; **lite LLM+rule** (модель видна, промпт крошечный); latency_ms в ответе |

### Фронт (приложение МТС)

- [x] Заглушка входа в приложение МТС: номер спрашивается один раз при запуске (без повторной авторизации на подключении)
- [x] Каталог услуг (вторая карточка-заглушка) + выход из услуги обратно в каталог
- [x] Карточка подключения услуги «AI менеджер звонков»
- [x] Оферта + согласие; без галочки «Подключить» не срабатывает
- [x] После подключения — дашборд / история / шаблоны / настройки
- [x] Настройки пишутся в `POST /service/settings` (бот только читает)
- [x] Кнопка «Перейти в Telegram-бота» только после подключения (`TG_BOT_URL`)
- [x] Тесты UI: `python -m tests.test_service_page`

### Бэкенд vs ТЗ

| ТЗ (обязательное) | Бэк | Как закрыто |
|---|---|---|
| Простота ≤ 5 мин | да | `/ready` чеклист + README /health |
| Маршрутизация голос / Telegram-чат / человек | да | `action_required` + `routing_rules` |
| Точность расшифровки / суть | да | Whisper + `summary` |
| Контроль: история + сценарии + правила | да | SQLite + `/scenarios` + `/routing_rules` |
| Конфиденциальность (демо) | да | всё локально, без облака на демо |
| CJM: уведомление Ивану | да | notify jsonl + `GET /notifications` + опц. Telegram |
| Усиление: аналитика | да | `GET /stats` + `GET /calls/stats` |
| Усиление: горячая линия | да | `POST /hotline` + правило |
| Усиление: обучение на примерах | да | `training_examples` → промпт |
| Комплаенс lite: аудит доступа | да | `GET /audit` |

## Сделано (к CP1)

### Telegram / фронт

- [x] `/start` — услуга активна на номере, клавиатура дашборда; бот **не** генерирует звонок сам
- [x] Дашборд: аналитика (`GET /calls/stats`), все звонки, только важные, карточка `/call id`
- [x] Настройки в боте — просмотр с линии (`GET /service/settings`); правка только во фронте
- [x] Регистрация чата Ивана (`data/tg_chats.txt` + `TG_CHAT_ID`)
- [x] Отчёт приходит с бэкенда после `process_call` / `process_call_voice`
- [x] Токен только из `.env` (`TG_BOT_TOKEN`), не в коде

### Локальный стек (бэк)

- [x] Локальный LLM: Ollama `qwen2.5:3b` + системный промпт Ивана (`LLM_PROVIDER=local`)
- [x] Локальный STT: faster-whisper `tiny` (`STT_PROVIDER=local`)
- [x] Локальный TTS: pyttsx3 / Windows SAPI (`TTS_PROVIDER=local`)
- [x] Structured JSON + fallback + disclosure + hard-routing guard + JSON-правила
- [x] История звонков SQLite + API
- [x] Сценарии `/scenarios`, правила `/routing_rules`, аналитика `/stats`, hotline `/hotline`
- [x] Notify Ивану (jsonl + опц. Telegram bot)
- [x] `process_call` / `process_call_voice` / `transcribe` / `synthesize`
- [x] Smoke: `tests/smoke_*.py` + `smoke_hard_routing.py`
- [x] Yandex опционально — на демо жюри не используем

## ТЗ → продукт

| Требование ТЗ / CJM | Статус |
|---|---|
| ИИ принимает входящие за Ивана | есть (текст и голос → агент) |
| Важное vs рутина | `is_critical`, фильтр `critical_only` |
| Точность расшифровки / суть | Whisper STT + `summary` |
| Ответ голосом звонящему | локальный TTS (демо-файл); в проде — стрим |
| Контроль: история звонков | SQLite + API + дашборд в приложении и Telegram |
| Маршрутизация голос / чат / человек | промпт + `action_required` + UI во фронте |
| Уведомление о записи разговора | всегда префикс перед `agent_response` (текст + голос) |
| Безопасность прототипа | локальная БД, `.gitignore`, ключи в `.env` |
| Онбординг ≤ 5 мин / UI сценариев | Flet: карточка → согласие → настройки / шаблоны |
| Telegram-уведомление Ивану | `/start` + отчёт с бэкенда после ручки |

## Безопасность БД (хакатон)

OK для демо: локальный файл, не в git, без ключей в таблице.  
В презентации: прод = контур МТС, Postgres, auth, шифрование, аудит доступа.

## Локальный запуск (обязательно)

1. Установить [Ollama](https://ollama.com/download) для Windows.
2. В терминале:
```bash
ollama pull qwen2.5:3b
ollama serve
```
3. Backend:
```bash
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```
4. Проверка: `GET /ready` → `ready=true` (и `demo_ready=true` когда Ollama с моделью)

### Ollama только на D: (в проекте)

Модели **не на C:** — в `D:\HUH\MTS_Hacaton_AI_Agent\.ollama\models`.

```powershell
cd D:\HUH\MTS_Hacaton_AI_Agent
powershell -ExecutionPolicy Bypass -File .\scripts\start_ollama_d.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\pull_qwen_d.ps1
```

Нужно свободно **~3+ ГБ на D:**. Архив `ollama-windows-amd64` после установки можно удалить с C:\Users\...\Downloads, чтобы освободить место.


Опционально в `.env`:
```
LLM_PROVIDER=local
STT_PROVIDER=local
TTS_PROVIDER=local
OLLAMA_MODEL=qwen2.5:3b
WHISPER_MODEL_SIZE=tiny
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## API для закрытия ТЗ (без Ollama)

- `GET /ready` — чеклист готовности демо (≤5 мин)
- `GET /api/v1/stats` — аналитика
- `GET /api/v1/calls/stats` — сводка для дашборда UI/бота
- `GET|PUT|DELETE /api/v1/routing_rules` — правила маршрутизации
- `GET|PUT|DELETE /api/v1/scenarios` — приветствие / FAQ
- `GET|PUT|DELETE /api/v1/training_examples` — обучение на примерах
- `POST /api/v1/hotline` — экстренный перевод на человека
- `GET|POST /api/v1/service/settings` — настройки линии (фронт пишет)
- `GET /api/v1/calls?critical_only=true` — история важных
- `GET /api/v1/notifications` — лента уведомлений Ивану
- `GET /api/v1/audit` — журнал доступа к карточкам/аудио
- `PATCH /api/v1/calls/{id}` — ручная правка резюме/ответа

## Дальше

1. Прогон на живом Ollama + демо для жюри
2. SpeechKit Realtime / стрим TTS в телефонию (опционально)
3. При наличии GPU — `OLLAMA_MODEL=qwen2.5:7b`
4. Прод-контур: Postgres, auth, без долгого хранения аудио
