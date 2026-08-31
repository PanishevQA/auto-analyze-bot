# Telegram-бот «Оценщик авто для перепродажи (РФ)»

Асинхронный Telegram-бот проводит пользователя через FSM-опрос, получает от YandexGPT
типичные неисправности, сырые цены ремонта и оценку риска, сравнивает рынок выбранного
региона со всей РФ и рассчитывает экономику сделки в Python. При недоступности официального
Market API используются локальные fallback-данные. Парсинг сайтов и другие LLM не используются.

## Требования

- Python 3.11 или новее;
- локальный PostgreSQL 15+;
- Telegram Bot Token и доступ к Yandex Cloud Foundation Models.

Docker не нужен и проект его не использует.

## Установка

```bash
python -m venv venv
source venv/bin/activate              # Windows PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## PostgreSQL

Создайте локальную БД и примените идемпотентную схему:

```bash
createdb auto_analyze
psql -d auto_analyze -f database/schema.sql
```

При запуске приложение также автоматически выполняет `schema.sql`. Таблица `ai_cache`
хранит ответы YandexGPT 24 часа; Redis не требуется.

## Переменные окружения

```bash
cp .env.example .env
```

Заполните обязательные `TELEGRAM_BOT_TOKEN`, `YANDEX_CLOUD_OAUTH_TOKEN`,
`YANDEX_CLOUD_FOLDER_ID` и `DATABASE_URL`. Необязательные `AUTO_RU_API_URL` и
`AUTO_RU_API_TOKEN` включают официальный Market API. Если URL отсутствует или запрос
завершается ошибкой, читается `config/fallback_prices.json`.

## Запуск из IDE или терминала

Выберите интерпретатор созданного виртуального окружения и запустите `main.py`, либо:

```bash
python main.py
```

Бот работает через aiogram long polling. Команда `/start` начинает выбор региона.

## Промпты

Шаблоны находятся в `prompts/`: `typical_issues.txt`, `repair_estimate.txt` и
`risk_assessment.txt`. Поля в фигурных скобках заполняются данными FSM. Литеральные
JSON-скобки должны быть удвоены (`{{` и `}}`), поскольку применяется `format_map`.
YandexGPT возвращает данные, а суммирование бюджета, прибыль и рентабельность вычисляет Python.

## Тестирование

```bash
pytest --cov=. --cov-report=term-missing
```

Интеграция с внешними сервисами построена через внедрение зависимостей `db`, `gpt` и
`market`, поэтому тесты не требуют реальных токенов или сетевого доступа.
