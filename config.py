from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'bot_database.db'}"
@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    owner_telegram_ids: frozenset[int] = frozenset()
    apipoint_api_url: str = "https://apipoint.ru/api/call"
    apipoint_token: str | None = None
    apipoint_cache_ttl_seconds: int = 3_600
    apipoint_connect_timeout: float = 5.0
    apipoint_read_timeout: float = 20.0
    apipoint_high_confidence_offers: int = 8
    apipoint_limited_confidence_offers: int = 3
    yandex_ai_endpoint: str | None = None
    yandex_ai_api_key: str | None = None
    yandex_vision_model_uri: str | None = None
    yandex_vision_connect_timeout: float = 10.0
    yandex_vision_read_timeout: float = 90.0
    yandex_vision_max_retries: int = 1
    yandex_vision_prompt_version: str = "vehicle-condition-v1"
    max_photos_per_analysis: int = 20
    min_photos_for_vision: int = 1
    max_photo_size_bytes: int = 10_485_760
    max_total_photos_size_bytes: int = 52_428_800
    quick_sale_coefficient: Decimal = Decimal("0.92")
    fixed_expenses_rub: int = 5_000
    risk_reserve_rub: int = 10_000
    target_profit_rub: int = 40_000
    excellent_price_margin_rub: int = 10_000
    test_mode: bool = False
    test_apipoint_scenario: str = "success"
    parts_price_cache_ttl_hours: int = 12
    parts_search_mode: str = "MANUAL_BROWSER"
    drom_baza_permission_confirmed: bool = False
    drom_baza_start_url: str = "https://baza.drom.ru/novosibirskaya-obl/sell_spare_parts/"
    parts_browser_headless: bool = True
    parts_browser_timeout_seconds: int = 30
    parts_browser_max_offers: int = 20
    parts_browser_max_pages: int = 1
    parts_browser_concurrency: int = 1
    parts_min_matched_offers: int = 3
    parts_match_confidence: Decimal = Decimal("0.80")
    parts_default_condition: str = "NEW"
    yandex_parts_prompt_version: str = "parts-query-v1"
    yandex_parts_model_uri: str | None = None
    yandex_parts_match_prompt_version: str = "parts-match-v1"
    yandex_parts_max_retries: int = 1

    @classmethod
    def from_env(cls) -> "Settings":
        values = {
            "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "owner_telegram_ids": _parse_owner_ids(os.getenv("OWNER_TELEGRAM_IDS", "")),
            "apipoint_api_url": os.getenv("APIPOINT_API_URL", "https://apipoint.ru/api/call"),
            "apipoint_token": os.getenv("APIPOINT_TOKEN") or None,
            "apipoint_cache_ttl_seconds": _positive_int("APIPOINT_CACHE_TTL_SECONDS", 3_600),
            "apipoint_connect_timeout": _positive_float("APIPOINT_CONNECT_TIMEOUT", 5.0),
            "apipoint_read_timeout": _positive_float("APIPOINT_READ_TIMEOUT", 20.0),
            "apipoint_high_confidence_offers": _positive_int("APIPOINT_HIGH_CONFIDENCE_OFFERS", 8),
            "apipoint_limited_confidence_offers": _positive_int("APIPOINT_LIMITED_CONFIDENCE_OFFERS", 3),
            "yandex_ai_endpoint": os.getenv("YANDEX_AI_ENDPOINT") or None,
            "yandex_ai_api_key": os.getenv("YANDEX_AI_API_KEY") or None,
            "yandex_vision_model_uri": os.getenv("YANDEX_VISION_MODEL_URI") or None,
            "yandex_vision_connect_timeout": _positive_float("YANDEX_VISION_CONNECT_TIMEOUT", 10.0),
            "yandex_vision_read_timeout": _positive_float("YANDEX_VISION_READ_TIMEOUT", 90.0),
            "yandex_vision_max_retries": _nonnegative_int("YANDEX_VISION_MAX_RETRIES", 1),
            "yandex_vision_prompt_version": os.getenv("YANDEX_VISION_PROMPT_VERSION", "vehicle-condition-v1"),
            "max_photos_per_analysis": _positive_int("MAX_PHOTOS_PER_ANALYSIS", 20),
            "min_photos_for_vision": _positive_int("MIN_PHOTOS_FOR_VISION", 1),
            "max_photo_size_bytes": _positive_int("MAX_PHOTO_SIZE_BYTES", 10_485_760),
            "max_total_photos_size_bytes": _positive_int("MAX_TOTAL_PHOTOS_SIZE_BYTES", 52_428_800),
            "quick_sale_coefficient": _decimal_between_zero_one("QUICK_SALE_COEFFICIENT", "0.92"),
            "fixed_expenses_rub": _nonnegative_int("FIXED_EXPENSES_RUB", 5_000),
            "risk_reserve_rub": _nonnegative_int("RISK_RESERVE_RUB", 10_000),
            "target_profit_rub": _nonnegative_int("TARGET_PROFIT_RUB", 40_000),
            "excellent_price_margin_rub": _nonnegative_int("EXCELLENT_PRICE_MARGIN_RUB", 10_000),
            "test_mode": _strict_bool("TEST_MODE", False),
            "test_apipoint_scenario": os.getenv("TEST_APIPOINT_SCENARIO", "success").lower(),
            "parts_price_cache_ttl_hours": _positive_int("PARTS_PRICE_CACHE_TTL_HOURS", 12),
            "parts_search_mode": os.getenv("PARTS_SEARCH_MODE", "MANUAL_BROWSER").upper(),
            "drom_baza_permission_confirmed": _strict_bool("DROM_BAZA_PERMISSION_CONFIRMED", False),
            "drom_baza_start_url": os.getenv("DROM_BAZA_START_URL", "https://baza.drom.ru/novosibirskaya-obl/sell_spare_parts/"),
            "parts_browser_headless": _strict_bool("PARTS_BROWSER_HEADLESS", True),
            "parts_browser_timeout_seconds": _positive_int("PARTS_BROWSER_TIMEOUT_SECONDS", 30),
            "parts_browser_max_offers": _positive_int("PARTS_BROWSER_MAX_OFFERS", 20),
            "parts_browser_max_pages": _positive_int("PARTS_BROWSER_MAX_PAGES", 1),
            "parts_browser_concurrency": _positive_int("PARTS_BROWSER_CONCURRENCY", 1),
            "parts_min_matched_offers": _positive_int("PARTS_MIN_MATCHED_OFFERS", 3),
            "parts_match_confidence": _decimal_between_zero_one("PARTS_MATCH_CONFIDENCE", "0.80"),
            "parts_default_condition": os.getenv("PARTS_DEFAULT_CONDITION", "NEW").upper(),
            "yandex_parts_prompt_version": os.getenv("YANDEX_PARTS_PROMPT_VERSION", "parts-query-v1"),
            "yandex_parts_model_uri": os.getenv("YANDEX_PARTS_MODEL_URI") or os.getenv("YANDEX_VISION_MODEL_URI") or None,
            "yandex_parts_match_prompt_version": os.getenv("YANDEX_PARTS_MATCH_PROMPT_VERSION", "parts-match-v1"),
            "yandex_parts_max_retries": _nonnegative_int("YANDEX_PARTS_MAX_RETRIES",1),
        }
        missing = [key for key in ("telegram_bot_token",) if not values[key]]
        if not values["owner_telegram_ids"]:
            missing.append("OWNER_TELEGRAM_IDS")
        if missing:
            raise RuntimeError(f"Не заданы обязательные переменные: {', '.join(missing)}")
        if values["max_photos_per_analysis"] > 20:
            raise RuntimeError("MAX_PHOTOS_PER_ANALYSIS не может превышать 20")
        if values["min_photos_for_vision"] > values["max_photos_per_analysis"]:
            raise RuntimeError("MIN_PHOTOS_FOR_VISION не может превышать MAX_PHOTOS_PER_ANALYSIS")
        if values["apipoint_limited_confidence_offers"] > values["apipoint_high_confidence_offers"]:
            raise RuntimeError("LIMITED confidence threshold не может превышать HIGH")
        if not values["test_mode"] and not values["apipoint_token"]:
            raise RuntimeError("APIPOINT_TOKEN обязателен при TEST_MODE=false")
        scenarios = {"success", "avgcarprice_no_result", "fallback_to_carprices", "all_sources_unavailable"}
        if values["test_apipoint_scenario"] not in scenarios:
            raise RuntimeError("Неизвестный TEST_APIPOINT_SCENARIO")
        if values["parts_search_mode"] not in {"DISABLED","MANUAL_BROWSER","AUTHORIZED_DROM_BROWSER"}:
            raise RuntimeError("Неизвестный PARTS_SEARCH_MODE")
        if values["parts_search_mode"] == "AUTHORIZED_DROM_BROWSER" and not values["drom_baza_permission_confirmed"]:
            raise RuntimeError("Автоматический поиск на Drom Базе нельзя включить без подтверждения разрешения правообладателя.")
        parsed=urlsplit(values["drom_baza_start_url"])
        if parsed.scheme != "https" or parsed.hostname != "baza.drom.ru" or parsed.username or parsed.password or parsed.port not in (None,443):
            raise RuntimeError("DROM_BAZA_START_URL должен использовать https://baza.drom.ru")
        if values["parts_browser_max_offers"] > 20 or values["parts_browser_max_pages"] > 1 or values["parts_browser_concurrency"] > 1:
            raise RuntimeError("Лимиты Drom browser не могут превышать 20 предложений, 1 страницу и concurrency=1")
        if values["parts_default_condition"] not in {"NEW","USED"}:
            raise RuntimeError("PARTS_DEFAULT_CONDITION должен быть NEW или USED")
        return cls(**values)


def _strict_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    if raw == "true": return True
    if raw == "false": return False
    raise RuntimeError(f"{name} должен иметь значение true или false")


def _parse_owner_ids(raw: str) -> frozenset[int]:
    try:
        values = frozenset(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as error:
        raise RuntimeError("OWNER_TELEGRAM_IDS должен содержать Telegram ID через запятую") from error
    if any(value <= 0 for value in values):
        raise RuntimeError("OWNER_TELEGRAM_IDS должен содержать положительные ID")
    return values


def _nonnegative_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} должен быть целым числом") from error
    if value < 0:
        raise RuntimeError(f"{name} не может быть отрицательным")
    return value


def _positive_int(name: str, default: int) -> int:
    value = _nonnegative_int(name, default)
    if value == 0:
        raise RuntimeError(f"{name} должен быть больше нуля")
    return value


def _positive_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} должен быть числом") from error
    if value <= 0:
        raise RuntimeError(f"{name} должен быть больше нуля")
    return value


def _decimal_between_zero_one(name: str, default: str) -> Decimal:
    try:
        value = Decimal(os.getenv(name, default))
    except InvalidOperation as error:
        raise RuntimeError(f"{name} должен быть десятичным числом") from error
    if not Decimal("0") < value <= Decimal("1"):
        raise RuntimeError(f"{name} должен быть больше 0 и не больше 1")
    return value
