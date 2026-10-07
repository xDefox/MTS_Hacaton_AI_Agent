# AI Call Agent — Трек 1 (CJM Иван Петров)

> **Кейс команды:** трек 1 — ИИ-агент для обработки **входящих** звонков.  
> Источники ТЗ: `docs/_tz_extract.txt` ← CJM + «Лекции_ТЗ_МТС.pdf» (стр. 3–5, 9–13).  
> Код: `main` = фронт (Flet) + бэк (YandexGPT / SpeechKit + local fallback) + Telegram-бот.

---

## Вердикт (на сейчас)

| Блок ТЗ | Статус | Комментарий |
|---|---|---|
| Обязательные требования трека 1 | **почти закрыты** | Онбординг, история, шаблоны↔LLM (per-line), правила, disclosure, демо-звонок |
| Усиление ценности | **закрыто в прототипе** | Аналитика, hotline (умный), правка карточки; training examples — API (UI опц.) |
| CJM путь Ивана | **демо закрывает** | Подключение → шаблоны/правила → TG → звонок → история/правка |
| Прод-оператор (SIP, биллинг, 99.9%) | **narrative на защите** | В коде не делаем; слайды + модульный контракт (Media / Control / Events) |

**Остаток до защиты:** свести UI dropdown «голос/текст/гибрид» ↔ поведение агента; репетиция e2e; скрины в питч.

---

## Обязательные требования ТЗ (трек 1)

| # | Требование ТЗ | Статус | Где в продукте | Что доделать |
|---|---|---|---|---|
| 1 | Простота подключения ≤ 5 мин | ✅ готово | Вход → каталог → согласие → Подключить; `/ready` | Живой тайминг на защите |
| 2 | Маршрутизация: голос **или** перевод в чат | 🟡 частично | UI: dropdown; бэк: `action_required` | Связать выбор UI с агентом; показать «ушли в TG» |
| 3 | Точность: ИИ понял **суть** | ✅ готово (демо) | STT (SpeechKit/Whisper) + `summary` + история; cleanup шума | 5–7 живых сценариев перед жюри |
| 4a | Интерфейс: **история звонков** | ✅ готово | Flet «История» + бот; фильтр `line_phone` | — |
| 4b | Интерфейс: **редактирование сценариев** | ✅ готово | UI CRUD → `/scenarios`; бэк: **per-line templates** + фильтр мата | — |
| 4c | Интерфейс: **настройка правил** | ✅ готово | Блок в «Настройки» → `/routing_rules` | — |
| 5 | Конфиденциальность | ✅ готово (прототип) | `.env`, согласие, disclosure **раз за сессию**, fallback локально | Слайд: ЦОД МТС на проде |

### Усиление ценности

| Требование | Статус | Где | Доделать |
|---|---|---|---|
| Аналитика / классификация | ✅ | Дашборд Flet + бот, `/calls/stats` | — |
| Обучение на примерах | 🟡 | API `/training_examples` → промпт | UI опц. |
| Экстренный перевод на человека | ✅ умная заглушка | Hotline: оффтоп/приманка → clarify, не эскалация; баннер в UI | Реальный handoff не нужен |

---

## CJM Ивана → наш продукт

| Этап CJM | Боль / ожидание | У нас | Статус |
|---|---|---|---|
| 1. Осознание | Страх «непрофессионально» | Питч-дек | ✅ pptx |
| 2. Поиск | Демо | TG голос↔голос | ✅ / ⬜ видео |
| 3. Подключение | ≤5 мин, сценарии, правила, TG | Flet + persistent `connected` | ✅ |
| 4. Первое использование | Пуш + резюме + правка | История + `PATCH /calls/{id}` | ✅ |
| 5. Регулярно | Горячая линия | Hotline + баннер-заглушка | ✅ |
| 6. Оценка | Масштаб / CRM | Слайды интеграция/монетизация | ✅ pptx |

---

## Что уже готово

### Приложение МТС (Flet)

- [x] Онбординг, каталог, `connected` по номеру
- [x] Вкладки: Дашборд / История / Шаблоны / Настройки
- [x] Шаблоны CRUD (add / edit / toggle / delete) → `/scenarios`
- [x] Правила внутри Настроек; routing hint (голос/текст/гибрид)
- [x] История линии + правка карточки + баннер эскалации
- [x] Telegram-кнопка после подключения

### Telegram-бот

- [x] Дашборд / история / настройки линии
- [x] Демо-звонок: голосовое приветствие → ГС → STT+LLM+TTS → история
- [x] Fallback текста; STT fallback Whisper при отсутствии YC_*

### Бэкенд

- [x] YandexGPT + SpeechKit; fallback Whisper / pyttsx3
- [x] Per-line templates в промпт + content filter
- [x] Disclosure ИИ один раз за сессию
- [x] Умный hotline (bait/unclear → clarify)
- [x] STT audio cleanup; routing rules; training examples
- [x] CallLog по `line_phone`; `/ready`

### Документы / защита

- [x] Питч: `docs/presentation_track1.pptx` (+ outline, `scripts/build_presentation.py`)
- [ ] Скрины / имена команды в слайдах
- [ ] Репетиция e2e

### Тесты

- [x] UI service page, API/LLM contract, routing fixtures, speech session

---

## Роадмап

### P0 — до защиты

1. ~~Шаблоны ↔ LLM~~ ✅ per-line templates + UI `/scenarios`
2. ~~UI правил / правка / эскалация / питч~~ ✅
3. **Свести маршрутизацию UI ↔ агент** — dropdown голос/текст/гибрид влияет на `action_required`
4. **Репетиция демо** — uvicorn + ключи YC / fallback + Flet + бот
5. **Питч добить** — скрины, команда; усилить «Иван управляет» после проверки шаблонов в live

### P1

6. UI training examples (опц.)
7. Видео/GIF демо
8. Явный «ушли в TG-чат» в боте при `offer_telegram_chat`

### P2 — прод / narrative

9. SIP adapter (Media) + streaming STT/TTS + barge-in  
10. Биллинг / МТС ID / ЦОД / Postgres  
11. Горизонталь: adapters (SIP, CRM, WhatsApp) на одном Call Agent Core  

---

## Архитектура для МТС (продажа)

Модуль **Call Intelligence**, не монолит АТС:

| Контракт | Сейчас | Прод |
|---|---|---|
| Control API | settings, rules, scenarios, history, patch | то же |
| Dialog API | turn-based `process_call(_voice)` | + realtime stream |
| Events | TG notify / history | webhooks → биллинг/CRM |
| Adapters | Flet, Telegram | + SIP/media gateway МТС |

TG-демо = turn-based эмуляция трубки. SIP = тот же core, другой транспорт.

---

## Критерии жюри → ответ

| Критерий | Как закрываем |
|---|---|
| Соответствие ТЗ | Таблица обязательных; P0 #3 — последний технический gap |
| Боль Ивана | Демо-звонок + важные + правка |
| Готовность к интеграции | Слайд: каналы МТС уже UX; SIP/биллинг — roadmap + 3 интерфейса |
| Монетизация | Услуга в каталоге / с баланса (narrative) |

---

## API (кратко)

- `GET /ready` · `POST process_call` · `process_call_voice` · `synthesize`
- `GET/PATCH /calls` · `/calls/stats` · `service/settings`
- `routing_rules` · `scenarios` · `training_examples` · `hotline`

## Запуск демо

```bash
# .env: YC_FOLDER_ID, YC_API_KEY (или local fallback STT/TTS)
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
python -m frontend.app
python -m frontend.tg_bot
```

`GET /ready` → желательно `demo_ready=true` при полном Yandex-стеке.

---

## Легенда

- ✅ готово в прототипе  
- 🟡 частично  
- ⬜ не сделано (видео / прод)
