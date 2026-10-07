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
| Скорость | В ТЗ нет «SLA ответа LLM», есть QoS линии + «быстро просматривает резюме» Иван | Короткий промпт, `num_ctx`/`num_predict`, `keep_alive`; GPU/`7b` опционально |

| ТЗ (обязательное) | Бэк | Как закрыто |
|---|---|---|
| Простота ≤ 5 мин | да | `/ready` чеклист + README /health |
| Маршрутизация голос / Telegram-чат / человек | да | `action_required` + `routing_rules` |
| Точность расшифровки / суть | да | Whisper + `summary` |
| Контроль: история + сценарии + правила | да | SQLite + `/scenarios` + `/routing_rules` |
| Конфиденциальность (демо) | да | всё локально, без облака на демо |
| CJM: уведомление Ивану | да | notify jsonl + `GET /notifications` + опц. Telegram |
| Усиление: аналитика | да | `GET /stats` |
| Усиление: горячая линия | да | `POST /hotline` + правило |
| Усиление: обучение на примерах | да | `training_examples` → промпт |
| Комплаенс lite: аудит доступа | да | `GET /audit` |

## Сделано (к CP1)

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
- `GET|PUT|DELETE /api/v1/routing_rules` — правила маршрутизации
- `GET|PUT|DELETE /api/v1/scenarios` — приветствие / FAQ
- `GET|PUT|DELETE /api/v1/training_examples` — обучение на примерах
- `POST /api/v1/hotline` — экстренный перевод на человека
- `GET /api/v1/calls?critical_only=true` — история важных
- `GET /api/v1/notifications` — лента уведомлений Ивану
- `GET /api/v1/audit` — журнал доступа к карточкам/аудио
- `PATCH /api/v1/calls/{id}` — ручная правка резюме/ответа

## Дальше

1. Прогон на живом Ollama + демо для жюри  
2. Стыковка с фронтом (UI сценариев / истории)  
3. При наличии GPU — `OLLAMA_MODEL=qwen2.5:7b`  
