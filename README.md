# МТС × Space Acc — Трек 1: ИИ-секретарь входящих звонков

[![Tests](https://github.com/xDefox/MTS_Hacaton_AI_Agent/actions/workflows/tests.yml/badge.svg)](https://github.com/xDefox/MTS_Hacaton_AI_Agent/actions/workflows/tests.yml)

Секретарь на линии для Ивана Петрова (малый IT-бизнес): поднимает трубку, понимает суть, отвечает голосом или ведёт в чат, пушит важное в Telegram, даёт историю и сценарии в «приложении МТС».

Подробная теория для защиты: [`docs/project_brief.md`](docs/project_brief.md)  
Питч: [`docs/presentation_outline.md`](docs/presentation_outline.md) · задачи: [`docs/tasks.md`](docs/tasks.md)

---

## Стек

| Слой | Технологии |
|------|------------|
| API | Python, FastAPI, Uvicorn, SQLite |
| LLM / речь | YandexGPT + SpeechKit STT/TTS (fallback: Whisper / pyttsx3) |
| Живой звонок | WebSocket `/call`, VAD, barge-in |
| UI | Flet (web :8550), лёгкий HTML `/app` для QR |
| Уведомления | Telegram-бот (aiogram), привязка только по `bind_token` |
| Android | `mobile/` → `flet build apk` (UI → публичный API) |

---

## Быстрый старт

```bash
# 1) зависимости
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2) секреты
copy .env.example .env   # заполнить YC_FOLDER_ID, YC_API_KEY, опц. TG_*

# 3) API
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 4) приложение МТС (Flet)
python -m frontend.app
# http://127.0.0.1:8550/

# 5) Telegram-бот (опционально)
python -m frontend.tg_bot
```

Проверки:

- Swagger: http://127.0.0.1:8000/docs  
- Готовность демо: http://127.0.0.1:8000/ready  
- Живой звонок: http://127.0.0.1:8000/call  
- Лёгкий веб для телефона/QR: http://127.0.0.1:8000/app  

Без ключей Yandex стек откатится на локальный STT/TTS и упрощённый LLM-ответ.

---

## Демо для жюри (без вашего Wi‑Fi)

```powershell
# tunnel на лёгкий веб :8000 (/app), не на тяжёлый Flet
.\scripts\start_demo_tunnel.ps1
# DEMO_WEB_URL=https://….trycloudflare.com → .env
python scripts\make_demo_qr.py
```

Telegram: только ключ из приложения («Перейти в Telegram»). Голый `/start` — отказ.

---

## Android APK

```powershell
.\scripts\prepare_mobile.ps1   # синк UI + API URL из DEMO_WEB_URL
cd mobile
flet build apk --yes --python-version 3.13 --permissions microphone
```

Нужны JDK 17 и Android SDK. APK ходит на публичный `API_BASE` (тот же host, что tunnel), не на `127.0.0.1`.

---

## Структура

```
backend/           # FastAPI, агент, STT/TTS, история, правила
frontend/          # Flet UI, TG-бот, assets голосового embed
mobile/            # точка входа для flet build apk
scripts/           # QR, tunnel, prepare_mobile, презентация
docs/              # ТЗ, CJM, brief, питч
tests/             # смоук / контракты
data/              # локально (gitignore): БД, TTS, tg_*
```

---

## Основные API

- `POST /api/v1/process_call` · `process_call_voice` · `synthesize`
- `GET/PATCH /api/v1/calls` · `/calls/stats`
- `GET/PUT /api/v1/service/settings` · `routing_rules` · `scenarios`
- WebSocket ` /api/v1/live_call/ws` — живой диалог
- Telegram: register / status / bind_token

---

## Архитектура одной фразой

**Call Intelligence** (Control / Dialog / Events), не монолит АТС: сейчас транспорт = веб/TG; на проде тот же core + SIP-адаптер и биллинг МТС.

---

## Команда и коммиты

Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`.

Авторы коммитов — участники команды. В сообщения **не** добавляем `Co-authored-by: Cursor` (иначе Cursor попадает в GitHub Contributors).
