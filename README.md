# Auto Analyze Bot

Личный асинхронный Telegram-бот для детерминированной оценки экономики покупки автомобиля
под перепродажу. Текущая реализация соответствует этапу **P0 — достоверная экономика**.

## Что реализовано в P0

- aiogram 3, SQLite и async SQLAlchemy 2;
- обязательный allowlist владельцев по Telegram ID;
- доменные Pydantic-модели с запретом лишних полей;
- APIpoint strategy: Avgcarprice → Carprices, один retry и TTL-кэш;
- полностью конфигурируемые URL, параметры, авторизация и путь к цене APIpoint;
- локальный версионируемый справочник видимых дефектов;
- финансовые формулы на `Decimal` и verdict `BUY`, `WATCH`, `PASS`, `NO_RESULT`;
- сохранение истории и ограничение пятью последними расчетами владельца.

LLM не формирует рынок, стоимость ремонта, прибыль, ROI, цену входа или verdict. Если APIpoint
не настроен либо оба endpoint недоступны, результат — `NO_RESULT`; нулевая или придуманная
рыночная цена не подставляется.

## Ограничения текущего этапа

Фотографии, vision-модель, Drom manual flow, идемпотентные платные callbacks и пересчет истории
относятся к P1 и пока не подключены. Существующая анкета продолжает собирать базовые ручные
данные. Официальный Drom API не реализован: контракт и письменное разрешение отсутствуют.

## Установка (Windows PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

## Обязательная конфигурация

Минимально заполните:

```env
TELEGRAM_BOT_TOKEN=
OWNER_TELEGRAM_IDS=123456789
```

Если `OWNER_TELEGRAM_IDS` пуст, приложение завершится с понятной ошибкой и не запустится
публично. Несколько ID разделяются запятыми.

### APIpoint

Репозиторий не содержит подтвержденного контракта APIpoint, поэтому URL, имена параметров,
авторизация и JSON-путь к цене намеренно не зашиты в код. Для каждого доступного endpoint
нужно заполнить значения из документации вашего аккаунта:

```env
APIPOINT_AVGCARPRICE_URL=
APIPOINT_AVGCARPRICE_PRICE_PATH=
APIPOINT_AVGCARPRICE_PARAM_MAP={"make":"...","model":"...","year":"..."}
APIPOINT_CARPRICES_URL=
APIPOINT_CARPRICES_PRICE_PATH=
APIPOINT_CARPRICES_PARAM_MAP={"make":"...","model":"...","year":"..."}
APIPOINT_AUTH_HEADER=
APIPOINT_AUTH_VALUE=
```

`*_PRICE_PATH` — путь к целому значению цены через точку, например `data.price`, только если
это подтверждено реальным ответом. `*_PARAM_MAP` сопоставляет канонические внутренние поля
с фактическими именами query-параметров APIpoint. Секреты не коммитьте.

## Финансовые настройки

```env
QUICK_SALE_COEFFICIENT=0.92
FIXED_EXPENSES_RUB=5000
RISK_RESERVE_RUB=10000
TARGET_PROFIT_RUB=40000
EXCELLENT_PRICE_MARGIN_RUB=10000
```

Формулы находятся только в `services/deal_engine.py`. В `total_investment`, break-even и max
buy включены ремонт, фиксированные расходы и резерв риска. Отрицательный ROI сохраняет знак.

## Запуск

```powershell
.\venv\Scripts\activate
python main.py
```

SQLite-файл `bot_database.db` создается автоматически и исключен из git.

## Команды

| Команда | Назначение |
|---|---|
| `/start` | Выбор региона и начало ручной анкеты. |
| `/history` | До пяти последних расчетов владельца. |
| `/history <ID>` | Детальный сохраненный отчет владельца. |

## Тестирование

```powershell
python -m compileall -q .
pytest -q
pytest --cov=. --cov-report=term-missing
```

Тесты используют `httpx.MockTransport`; реальные платные запросы не выполняются.
Файлы `tests/fixtures/apipoint_*.json` являются только тестовыми схемами, связанными с
явно настроенными тестовыми adapters, и не заявляются как реальный контракт APIpoint.

## Следующий этап

Для P1 владельцу потребуются URI мультимодальной Qwen-модели и проверенные параметры Responses
API. Для подключения APIpoint нужны обезличенные fixtures реальных ответов. Для официального
Drom adapter дополнительно необходимы письменное разрешение и подтвержденный API-контракт.
