# Telegram-бот «Оценщик авто для перепродажи (РФ)»

Перечень функций, добавленных в текущей поставке, опубликован в
[`CHANGELOG.md`](CHANGELOG.md).

Асинхронный бот для предварительной оценки экономики перепродажи подержанного автомобиля.
Он сравнивает рынок выбранного региона со всей Россией, запрашивает у YandexGPT только
исходные сведения о ремонте и рисках, а все финансовые расчеты выполняет в Python.

## Возможности

- пошаговый опрос с проверкой модели, года, пробега и цены;
- выбор одного из шести регионов;
- рыночные данные из официального API или локального fallback-файла;
- смета, оценка риска, чек-лист осмотра и ссылки только на поисковые страницы запчастей;
- история пяти последних расчетов с защитой по Telegram ID;
- автоматическая локальная база SQLite без отдельного сервера.

## Требования

- Windows 10 или Windows 11;
- Python 3.11 или новее;
- Telegram-бот и учетная запись Yandex Cloud с доступом к Foundation Models.

## Установка в Windows PowerShell

Откройте PowerShell в каталоге проекта и выполните:

```powershell
python -m venv venv
.\venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Если выполнение скриптов запрещено, разрешите его только для текущего процесса:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\activate
```

## Настройка переменных окружения

Создайте рабочий файл настроек:

```powershell
copy .env.example .env
notepad .env
```

Обязательные поля:

| Поле | Назначение и получение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Создайте бота через [@BotFather](https://t.me/BotFather), выполните `/newbot` и скопируйте токен. |
| `YANDEX_CLOUD_FOLDER_ID` | Откройте нужный каталог в [консоли Yandex Cloud](https://console.yandex.cloud/); идентификатор указан на странице каталога. |
| `YANDEX_CLOUD_API_KEY` | Рекомендуемый способ: создайте API-ключ сервисного аккаунта с доступом к Foundation Models. |
| `YANDEX_CLOUD_OAUTH_TOKEN` | Альтернатива API-ключу: получите OAuth-токен по [инструкции Yandex Cloud](https://yandex.cloud/ru/docs/iam/concepts/authorization/oauth-token). Достаточно заполнить один из двух типов ключей. |
| `YANDEXGPT_ENDPOINT` | URL OpenAI-совместимого Chat Completions API. По умолчанию: `https://ai.api.cloud.yandex.net/v1/chat/completions`. |

`AUTO_RU_API_URL` и `AUTO_RU_API_TOKEN` необязательны и предназначены только для
официально предоставленного API. Без них бот использует `config/fallback_prices.json`.
Настраивать путь к SQLite не требуется.

При наличии API-ключа бот использует заголовок `Api-Key`. OAuth-токен не отправляется
напрямую в Foundation Models: бот асинхронно обменивает его на краткоживущий IAM-токен
и передает модели IAM-токен по схеме `Bearer`. Секреты не
записываются в журнал. Если ни официальный Market API, ни локальная запись для автомобиля
не найдены, YandexGPT возвращает только наборы сырых рыночных цен, а средние значения,
диапазон и цену быстрой продажи вычисляет Python.

## Запуск

```powershell
.\venv\Scripts\activate
python main.py
```

При первом запуске рядом с `main.py` автоматически создается `bot_database.db`.

## Команды бота

| Команда | Назначение |
|---|---|
| `/start` | Регистрация, выбор региона и начало нового анализа. |
| `/history` | Список не более пяти последних расчетов текущего пользователя. |
| `/history <ID>` | Детальный отчет по указанному ID, если он принадлежит пользователю. |

## Структура проекта

```text
main.py                         точка запуска aiogram
config.py                       переменные окружения и путь SQLite
handlers/start.py               команда /start и регионы
handlers/questionnaire.py       FSM-опрос и подтверждение
handlers/analysis.py            анализ и сохранение отчета
handlers/history.py             безопасный просмотр истории
database/models.py              async SQLAlchemy-модели и создание БД
database/queries.py             запросы, JSON-сериализация и лимит истории
services/yandex_gpt.py          YandexGPT, JSON-разбор и повторы
services/market_api.py          официальный API и fallback
services/calculator.py          финансовая математика Python
services/link_generator.py      ссылки на поисковую выдачу
prompts/                        редактируемые шаблоны YandexGPT
config/fallback_prices.json     резервные рыночные цены
tests/                          автоматические тесты
```

В JSON-примерах промптов литеральные фигурные скобки записываются как `{{` и `}}`,
поскольку шаблоны заполняются методом `format_map`.

## База данных и история

SQLite хранится в файле `bot_database.db`; JSON-поля сериализуются как текст. После каждой
записи бот оставляет только пять новейших расчетов конкретного пользователя. Запрос детального
отчета одновременно фильтруется по ID расчета и Telegram ID владельца.

Для просмотра остановите бота, установите
[DB Browser for SQLite](https://sqlitebrowser.org/dl/), откройте `bot_database.db` и выберите
вкладку **Browse Data**. Не редактируйте базу во время работы бота.

## Резервное копирование

Сначала остановите бота сочетанием `Ctrl+C`, затем выполните:

```powershell
New-Item -ItemType Directory -Force backup
Copy-Item .\bot_database.db .\backup\bot_database.db
```

Для восстановления при остановленном боте:

```powershell
Copy-Item .\backup\bot_database.db .\bot_database.db -Force
```

## Устранение неполадок

### Команда `python` не найдена

Переустановите Python с [python.org](https://www.python.org/downloads/windows/) и включите
флажок **Add Python to PATH**. Перезапустите PowerShell и проверьте `python --version`.

### Не активируется виртуальное окружение

Выполните `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, затем повторите
`.\venv\Scripts\activate`. Настройка действует только до закрытия окна.

### Бот сообщает о незаданных переменных

Убедитесь, что файл называется именно `.env`, расположен рядом с `main.py`, а значения после
знака `=` не заключены в кавычки и не содержат лишних пробелов.

### Ошибка авторизации Yandex Cloud

Обновите API-ключ либо OAuth-токен, проверьте endpoint, ID каталога и доступ сервисного
аккаунта к Foundation Models. Модель
зафиксирована как `yandexgpt-5.1/latest` и не требует настройки в `.env`.
Если токен когда-либо был опубликован в чате, логе или репозитории, немедленно отзовите его
и создайте новый — удаление сообщения не делает раскрытый секрет снова безопасным.

### Файл базы заблокирован

Закройте DB Browser for SQLite или отмените в нем незавершенную транзакцию, затем перезапустите
бота. Не храните рабочую базу в каталоге, который одновременно синхронизируется несколькими ПК.

## Тестирование

```powershell
pytest --cov=. --cov-report=term-missing
```
