# MTS Hackathon × Space — Track 1

ИИ-агент входящих звонков для IT-предпринимателя **Ивана Петрова**.

Стек: **Python + FastAPI + локальный Ollama (Qwen2.5) + Whisper STT + local TTS + SQLite**.  
По умолчанию **без внешних API** (контур под требования жюри МТС). Системный промпт по CJM/ТЗ.

## Что умеет сейчас

`POST /api/v1/process_call` — текст → ответ ИИ (+ опц. TTS).  
`POST /api/v1/process_call?with_audio=true` — то же + озвучка ответа.  
`POST /api/v1/process_call_voice` — аудио → STT → агент → TTS ответа → история.  
`POST /api/v1/transcribe` — только голос → текст.  
`POST /api/v1/synthesize` — произвольный текст → речь.

| Поле | Смысл по ТЗ |
|------|-------------|
| `transcript` | Распознанная речь (только voice-эндпоинты) |
| `agent_response` | Что говорит агент звонящему |
| `is_critical` / `priority` | Важное обращение или рутина |
| `intent` | Категория (коммерция, жалоба, спам, эскалация…) |
| `action_required` | `continue_dialog` / `transfer_to_human` / `offer_telegram_chat` / `callback_recommended` |
| `summary` | Краткое резюме для Telegram Ивану |
| `audio_url` | Ссылка на озвучку ответа (демо TTS) |
| `call_id` | ID записи в локальной истории |

История звонков (ТЗ: контроль и управление):

- `GET /api/v1/calls` — список (новые сверху)
- `GET /api/v1/calls?critical_only=true` — только важные
- `GET /api/v1/calls?session_id=...` — реплики одной сессии
- `GET /api/v1/calls/{id}` — детали карточки
- `PATCH /api/v1/calls/{id}` — ручная правка резюме/ответа
- `GET /api/v1/calls/{id}/audio` — озвучка ответа агента (если была сгенерирована)
- `GET /api/v1/notifications` / `GET /api/v1/audit` / `GET /api/v1/stats`
- `GET /ready` — чеклист готовности демо (≤ 5 мин)

## Быстрый старт (≤ 5 минут)

1. Python 3.10+
2. Установка:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Установите [Ollama](https://ollama.com/download), затем:
```bash
ollama pull qwen2.5:3b
ollama serve
```
4. (Опционально) `.env`: `LLM_PROVIDER=local`, `STT_PROVIDER=local`, `TTS_PROVIDER=local`.
5. Запуск API:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

6. Swagger: http://127.0.0.1:8000/docs  
7. Готовность: http://127.0.0.1:8000/ready → `ready=true`, после pull модели `demo_ready=true`  
8. Health: http://127.0.0.1:8000/health → `llm_provider=local`

### Ollama только на D: (важно при полном C:)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_ollama_d.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\pull_qwen.ps1
```

Модели: `D:\HUH\MTS_Hacaton_AI_Agent\.ollama\models`  
Кэш Whisper: `D:\HUH\MTS_Hacaton_AI_Agent\.cache\huggingface`

### Голос (локально по умолчанию)

- `POST /api/v1/transcribe` — аудио → текст (Whisper)  
- `POST /api/v1/synthesize` — текст → речь (pyttsx3)  
- `POST /api/v1/process_call_voice` — аудио → STT → агент → TTS  
- `GET /api/v1/calls/{id}/audio` — скачать озвучку ответа  

**Куда кладём аудио (демо):** `data/tts/call_{id}.wav` — локально, в `.gitignore` через `data/`.  
**По ТЗ в проде:** TTS стримится звонящему в реальном времени (трубка / Voice Agent), файлы на диск не копятся.

В Swagger для STT — короткий `.ogg`/`.wav`. Без микрофона: `python tests/test_speech_session.py`.

### Пример запроса (текст + озвучка)

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/process_call?with_audio=true" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"demo-1\",\"user_message\":\"Соедините с менеджером, срочно по договору\",\"client_phone\":\"+79001112233\"}"
```

В ответе будет `audio_url` — открой его в браузере, чтобы услышать голос агента.

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
  services/speechkit_stt.py  # STT + TTS
  services/tts_storage.py    # data/tts/ для демо
tests/                    # smoke-тесты бэка
  smoke_test.py
  smoke_history.py
  smoke_voice.py
  smoke_tts.py
data/calls.db             # локально, не в git
data/tts/*.ogg            # озвучка ответов (демо), не в git
docs/                     # ТЗ, CJM, tasks.md
```

Ветка `feature/backend` — только бэкенд. Фронт (`frontend/`) живёт в `main`, его отсюда не трогаем.

## Данные и безопасность (прототип)

- История в `data/calls.db` (SQLite), папка в `.gitignore`.
- API-ключи только в `.env`, не в БД.
- Для продакшена / презентации жюри: контур МТС, Postgres, auth, шифрование, аудит доступа.

## Коммиты

Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.

## Дальше по ТЗ

- Telegram-уведомление Ивану (резюме + расшифровка)
- SpeechKit Realtime / стрим ответа в телефонию
- UI: дашборд истории, сценарии / правила маршрутизации
