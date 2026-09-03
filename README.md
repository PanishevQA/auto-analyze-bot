# Auto Analyze Bot — P1

Личный асинхронный Telegram-бот для предварительной оценки автомобиля под перепродажу.
Рынок получает только через APIpoint, видимое состояние — через Yandex AI Studio Qwen,
стоимость ремонта — из локального каталога, а деньги и verdict рассчитывает `DealEngine`.

## Безопасность и ограничения

- Доступ разрешен только `OWNER_TELEGRAM_IDS`.
- Drom работает исключительно в manual mode: ссылка валидируется и сохраняется, HTTP-запрос к Drom не выполняется.
- Фото не заменяют осмотр; vision не оценивает агрегаты, документы, юридическую чистоту или скрытые дефекты.
- LLM не определяет рынок, рублевый ремонт, прибыль, ROI, max buy или verdict.
- Бинарные фото и временные пути не сохраняются; временный каталог удаляется в `finally`.

## Установка (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
python main.py
```

## Обязательные настройки

```env
TELEGRAM_BOT_TOKEN=
OWNER_TELEGRAM_IDS=123456789
APIPOINT_API_URL=https://apipoint.ru/api/call
APIPOINT_TOKEN=
```

Без vision-настроек бот запускается в degraded mode: рынок и экономика работают, состояние
по фото получает `UNAVAILABLE`, поэтому выгодная экономика приводит к WATCH, а не BUY.

```env
YANDEX_AI_ENDPOINT=
YANDEX_AI_API_KEY=
YANDEX_VISION_MODEL_URI=gpt://<folder_id>/qwen3.6-35b-a3b
```

Остальные timeout, photo limit и финансовые значения перечислены в `.env.example`.

## Сценарий

1. `/start`, выбор региона и «Проанализировать авто».
2. Выбор Drom/manual; Drom-ссылка используется только как источник.
3. Отдельный ввод марки, модели, года, поколения, пробега, цены, двигателя, топлива,
   мощности, КПП, привода, кузова и описания.
4. Загрузка до 20 Telegram Photo/документов и управление списком.
5. Подтверждение платных запросов с idempotency key.
6. Параллельный APIpoint и vision, затем RepairCatalog и DealEngine.
7. Короткий и подробный отчет, сохранение в SQLite.
8. `/history <ID>` → «Пересчитать с другой ценой» без APIpoint и vision.

## APIpoint

`TEST_MODE=false` используется по умолчанию и требует `APIPOINT_TOKEN`. При
`TEST_MODE=true` создаётся детерминированный fake-клиент без сети; тестовый рынок
помечается 🧪 в отчёте и БД. TEST_MODE отключает только APIpoint: Yandex AI и
будущий официальный поставщик запчастей могут оставаться платными.

Клиент всегда выполняет последовательные POST на `APIPOINT_API_URL`:

- `sources=avgcarprice`, цена только из `result.avgcarprice.result.average`;
- при ошибке — `sources=carprices`, цена только из `result.carprices.result.avg_price`.

Верхние `price` и `balance` сохраняются как стоимость запроса и баланс, но никогда не
используются как рынок. Timeout/429/5xx получают максимум один retry; обычный 4xx — без retry.

## SQLite и миграция

`database/migrations.py` идемпотентно добавляет P1-колонки к старой таблице, не удаляя записи.
Хранятся normalized JSON, статусы блоков, версии, metadata фото и parent calculation.
Версия схемы записывается в `PRAGMA user_version`; миграция 3 добавляет test-mode,
котировки и metadata браузерного поиска без удаления старых строк.

## Цены запчастей

`repair_catalog.json` хранит стоимость работ, но не выдаётся за источник актуальных
цен деталей. Подготовлены модели, протокол поставщика, медианная нормализация,
TTL-кэш и безопасный `UNAVAILABLE`-режим. Когда замена требует детали, но надёжные
публичные предложения не переданы или не найдены, статическая цена не подставляется,
а `BUY` блокируется. Автоматические запросы к Drom не выполняются в `MANUAL_BROWSER`.

### Браузерные режимы

`PARTS_SEARCH_MODE` принимает `DISABLED`, `MANUAL_BROWSER` (по умолчанию) или
`AUTHORIZED_DROM_BROWSER`. Yandex AI Studio не является браузером: модель только
формирует структурированный запрос и проверяет релевантность недоверенных карточек.
В разрешённом автоматическом режиме локальным Chromium управляет Playwright, а
медиану и экономику по-прежнему рассчитывает Python.

`AUTHORIZED_DROM_BROWSER` запрещён без `DROM_BAZA_PERMISSION_CONFIRMED=true` и
специального разрешения правообладателя. CAPTCHA, Access Denied и сообщения о
необычном трафике немедленно останавливают поиск; обходов, proxy rotation,
fingerprinting, скрытых XHR и автоматического входа нет. Без разрешения ручной
режим лишь показывает Drom Базу и обрабатывает предоставленные владельцем данные.
Browser search не использует API поставщика, но вызовы Yandex AI Studio могут
оставаться платными. `TEST_MODE` отключает только APIpoint и никогда не включает
живой Drom browser автоматически.

Установка браузера для разрешённого режима:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Проверка

```powershell
python -m compileall -q .
pytest -q
pytest --cov=. --cov-report=term-missing
```

Все HTTP-тесты используют `httpx.MockTransport`; реальные платные запросы запрещены.

## Интеграционное ограничение Yandex

Payload Responses API изолирован в `YandexVisionClient.build_payload`. В среде разработки
официальная страница документации была недоступна через сетевой proxy (403), поэтому перед
первым платным запуском владелец должен сверить `input_image`/`json_schema` поля с актуальной
документацией своего Yandex AI Studio аккаунта и при необходимости изменить только builder.
