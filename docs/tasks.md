# AI Call Agent — рабочий roadmap (MTS Hackathon × Space)

> Источники: `docs/Лекции_ТЗ_МТС.pdf` (ТЗ), `docs/CJM_Хакатон.docx.pdf` (CJM).  
> Ветка бэка: `feature/backend`. Структура кода: **`backend/`** (пакет FastAPI Трека 1).

**Статус чекпоинта 1 (бэк + ИИ):** ✅ сдан  
YandexGPT подключён, системный промпт Ивана, smoke-тесты 3 сценариев проходят (`model: yandexgpt:rc`).

---

## 0. Контекст

| Параметр | Значение |
|---|---|
| **Трек** | **Трек 1 — «ИИ-агент для обработки входящих звонков» (CJM 1)** |
| Персонаж | Иван Петров, 42 года, владелец небольшой IT-компании |
| Его боль | Весь день на совещаниях/разъездах, не берёт неизвестные номера, но не хочет терять важных клиентов и партнёров |
| Цель продукта | Не пропускать важные обращения · экономить время на разбор звонков · профессиональное общение с каждым звонящим |
| Ключевой критерий | Флаг `is_critical` — ИИ отличает важный звонок от рутины и эскалирует его |
| Стек | FastAPI (Python) + YandexGPT (AI Studio) + фронт Flet/Web + Telegram (в плане) + SpeechKit (позже) |
| API | `POST /api/v1/process_call`, `GET /health` |

⚠️ **Фокус по ТЗ:** жюри проверяет решение по боли выбранного персонажа. Трек 2 (Алексей Морозов) — **не распыляться**.

---

## 1. Обязательные требования ТЗ (Definition of Done)

- [ ] **Простота подключения** — настройка «не более 5 минут» (мастер из коробки / понятный онбординг)
- [x] **Гибкость маршрутизации** — логика в промпте/API: голос (`continue_dialog`) **или** чат (`offer_telegram_chat`) **или** человек (`transfer_to_human`) · UI/Telegram ещё нет
- [x] **Суть обращения** — `summary` + классификация от YandexGPT (STT пока текстовая симуляция реплики звонящего)
- [~] **Контроль и управление** — история звонков в SQLite + API ✅ · редактирование сценариев / правила UI ещё нет
- [~] **Безопасность** — в промпте уведомление о записи/обработке; полный compliance-блок ещё в презентации

**Усиливающие ценность функции (делать ПОСЛЕ обязательных):**

- [ ] Аналитика: статистика по звонкам, классификация запросов, выявление частых вопросов
- [ ] Обучение ИИ на примерах реальных разговоров клиента
- [x] Экстренный перевод на человека («соедините с менеджером») — `action_required=transfer_to_human` (проверено smoke-тестом)

---

## 2. Соответствие CJM: боли → фичи

- [~] Этап 4–5: **резюме готово в API** (`summary`) · уведомление в Telegram/дашборде — ещё нет
- [ ] Этап 4: ручная корректировка ответов ИИ
- [x] Этап 5: «горячая линия» — логика эскалации в промпте + JSON
- [ ] Этап 3: пошаговый мастер настройки, шаблоны сценариев (приветствие, FAQ), правила маршрутизации
- [ ] Этап 3: интеграция с Telegram «в один клик»
- [~] Этап 5: приоритеты (`priority` / `is_critical`) считаются ИИ · UI настройки правил — ещё нет
- [ ] Этап 6: отчёты по звонкам

---

## 3. Архитектура проекта (актуальная)

```
MTS_Hacaton_AI_Agent/
│
├── backend/
│   ├── main.py                 # ✅ FastAPI + CORS + /health + init_db
│   ├── config.py               # ✅ YC_* + DATABASE_URL
│   ├── database.py             # ✅ SQLAlchemy / SQLite
│   ├── models.py               # ✅ CallLog
│   ├── schemas.py              # ✅ CallRequest / CallResponse / CallHistoryItem
│   ├── api/routes_call.py      # ✅ process_call + GET /calls
│   ├── prompts/system_ivan.py  # ✅ Системный промпт Трека 1
│   └── services/
│       ├── yandex_llm.py       # ✅ YandexGPT + JSON + fallback
│       └── call_history.py     # ✅ save / list / get
│
├── scripts/smoke_test.py       # ✅ LLM сценарии
├── scripts/smoke_history.py    # ✅ история после process_call
├── requirements.txt
├── .env.example
├── README.md
├── frontend/                   # Flet / Telegram (партнёр)
├── data/calls.db               # локально, не в git
└── docs/tasks.md
```

---

## 4. Этап 1 — Контракты и схемы — ✅ ГОТОВО

Файлы: [`backend/schemas.py`](../backend/schemas.py), [`backend/api/routes_call.py`](../backend/api/routes_call.py)

- [x] Модели вынесены в `backend/schemas.py`
- [x] Запрос: `session_id`, `user_message`, `client_phone`, опц. `dialog_history`
- [x] Ответ: `agent_response`, `is_critical`, `priority`, `intent`, `action_required`, `summary`, `caller_name`, `recommended_next_step`, `session_id`, `model`, `call_id`
- [x] `CallHistoryItem` / `CallHistoryList` для истории
- [x] Версия API: `/api/v1/...`

**Актуальный контракт `action_required`:**
- `continue_dialog` — продолжить голосом
- `offer_telegram_chat` — длинный/сложный → чат
- `transfer_to_human` — горячая линия
- `callback_recommended` — Ивану стоит перезвонить

**`intent`:** `commercial` | `support_request` | `complaint` | `faq` | `partnership` | `spam` | `wrong_number` | `escalation` | `other`

**Для фронта:** ориентироваться на этот JSON, не на старый `main.py`.

---

## 5. Этап 2 — Интеграция с LLM — ✅ ГОТОВО (чекпоинт 1)

Файлы: [`backend/services/yandex_llm.py`](../backend/services/yandex_llm.py), [`backend/prompts/system_ivan.py`](../backend/prompts/system_ivan.py)

- [x] Обёртка YandexGPT (AI Studio SDK), retries, structured JSON
- [ ] SpeechKit STT/TTS — следующий этап (голос)
- [x] Системный промпт: ИИ-секретарь Ивана Петрова, важность, маршрутизация, compliance-фраза о записи
- [x] Валидация ответа в pydantic-схему (все поля required — требование Yandex)
- [x] Fallback, если ключей нет / API упал — демо не падает
- [x] Smoke: `python scripts/smoke_test.py` → 3/3 с `model: yandexgpt:rc`

---

## 6. Этап 3 — Бизнес-логика — ✅ в промпте + LLM (отдельный call_logic.py не нужен)

- [x] `is_critical` / `priority` — считает YandexGPT по правилам промпта
- [x] `intent` — классификация
- [x] `action_required` — голос / чат / человек / перезвон
- [x] `summary` для Ивана
- [x] Эскалация «соедините с менеджером» → `transfer_to_human`

Проверено:
| Сценарий | Ожидание | Факт smoke |
|---|---|---|
| Алексей / Альфа / пилот | critical + commercial | ✅ |
| Реклама Директа | spam, не critical | ✅ |
| Соедините с менеджером | escalation + transfer | ✅ |

---

## 7. Этап 4 — База данных и история — ✅ ГОТОВО

> Закрывает ТЗ «Контроль и управление: история звонков».

- [x] SQLite (SQLAlchemy), файл `data/calls.db` (gitignore)
- [x] Сущность `CallLog`: id, session_id, caller_phone, user_message, agent_response, summary, is_critical, priority, intent, action_required, caller_name, recommended_next_step, model, created_at
- [x] `GET /api/v1/calls` — история (`critical_only` фильтр)
- [x] `GET /api/v1/calls/{id}` — детали
- [x] `POST /api/v1/process_call` сохраняет запись и возвращает `call_id`
- [ ] (опц.) `GET /api/v1/stats`

**Безопасность прототипа:** локальная БД без ключей; без auth на localhost; в презентации — контур оператора / Postgres / аудит.

---

## 8. Этап 5 — Фронтенд (дашборд Ивана) — ⬜ ЗОНА ПАРТНЁРА

**Стиль:** МТС — красный `#E30611`, тёмно-серый, белый.

Бэкенд для шагов 2 и 5 **уже готов** — можно бить в live API.

- [ ] **Шаг 1:** базовое окно Flet в цветах МТС
- [ ] **Шаг 2:** `frontend/api_client.py` — POST `/api/v1/process_call`
- [ ] **Шаг 3:** список звонков: `⚠️ Важно` / `ℹ️ Обычный` по `is_critical`
- [ ] **Шаг 4:** клик → резюме (`summary`) + текст разговора
- [ ] **Шаг 5:** CORS ок, данные рисуются (бэк CORS уже `allow_origins=["*"]`)
- [ ] Тумблер ИИ-агента: Активен / Неактивен
- [ ] Панель редактирования сценариев
- [ ] (опц.) Онбординг-мастер ≤ 5 минут

**Панель симуляции (демо):**

- [ ] Поле ввода реплики звонящего + шаблоны (как в `scripts/smoke_test.py`)
- [ ] Кнопка «Симулировать входящий звонок» → карточка: ответ ИИ + важность

Запуск бэка для фронта:
```powershell
.\.venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
# Swagger: http://127.0.0.1:8000/docs
```

---

## 9. Этап 6 — Compliance и оператор связи — ⬜ частично заложено

- [x] Уведомление звонящего о записи/обработке — в системном промпте (первая реплика)
- [ ] Локализация ПДн / тайна связи / согласие абонента / right to review — в презентацию
- [ ] SIP / биллинг / каналы МТС / масштаб / монетизация — слайд архитектуры
- [ ] Открытые регуляторные вопросы — явно в презентации

---

## 10. Этап 7 — Демо и презентация

- [ ] Соответствие ТЗ (все 5 must-have)
- [~] Понимание боли Ивана — промпт и сценарии уже про Трека 1
- [ ] Готовность к интеграции / монетизация / compliance-слайды
- [~] Качество демонстрации — API + smoke работают; нужен UI/симулятор
- [x] README с запуском чекпоинта 1
- [ ] ARCHITECTURE.md

---

## 11. Порядок работ (статус)

| # | Задача | Статус |
|---|---|---|
| 1 | Схемы/контракты API | ✅ |
| 2 | Структура `backend/` (config, services, routes) | ✅ |
| 3 | Бизнес-логика важности + маршрутизация (через LLM) | ✅ |
| 4 | YandexGPT + промпт Ивана + smoke | ✅ чекпоинт 1 |
| 5 | SQLite + история звонков | ✅ |
| 6 | Flet-дашборд: список, детали, тумблер | ☐ фронт (кормит `GET /calls`) |
| 7 | Панель симуляции звонка | ☐ фронт |
| 8 | Редактор сценариев/правил | ☐ |
| 9 | Compliance + «жизнь внутри оператора» | ☐ |
| 10 | ARCHITECTURE + финальная презентация | ☐ |

---

## 12. Открытые вопросы — решено / осталось

- [x] **LLM:** YandexGPT (AI Studio) — подключено
- [~] **STT:** пока текст в симуляторе / smoke; SpeechKit — следующий этап для голоса
- [~] **Фронт:** Flet-дашборд как основной UI; Telegram — уведомления (CJM), оба желательны
- [x] **SIP:** для хакатона достаточно текстовой симуляции входящего звонка; в презентации — путь к SIP оператора

---

## Как презентовать чекпоинт 1 (бэк)

> Подключили YandexGPT к FastAPI, написали системный промпт ИИ-секретаря Ивана (Трек 1).  
> На вход — реплика звонящего, на выход — JSON: ответ, важность, intent, маршрутизация, резюме для Ивана.  
> Три сценария (лид / спам / «соедините с менеджером») проходят на живой модели.
