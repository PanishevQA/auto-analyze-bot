from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'bot_database.db'}"
@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    owner_telegram_ids: frozenset[int] = frozenset()
    apipoint_avgcarprice_url: str | None = None
    apipoint_avgcarprice_price_path: str | None = None
    apipoint_avgcarprice_param_map: dict[str, str] | None = None
    apipoint_carprices_url: str | None = None
    apipoint_carprices_price_path: str | None = None
    apipoint_carprices_param_map: dict[str, str] | None = None
    apipoint_auth_header: str | None = None
    apipoint_auth_value: str | None = None
    apipoint_cache_ttl_seconds: int = 3_600
    apipoint_connect_timeout: float = 5.0
    apipoint_read_timeout: float = 20.0
    quick_sale_coefficient: Decimal = Decimal("0.92")
    fixed_expenses_rub: int = 5_000
    risk_reserve_rub: int = 10_000
    target_profit_rub: int = 40_000
    excellent_price_margin_rub: int = 10_000

    @classmethod
    def from_env(cls) -> "Settings":
        values = {
            "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "owner_telegram_ids": _parse_owner_ids(os.getenv("OWNER_TELEGRAM_IDS", "")),
            "apipoint_avgcarprice_url": os.getenv("APIPOINT_AVGCARPRICE_URL") or None,
            "apipoint_avgcarprice_price_path": os.getenv("APIPOINT_AVGCARPRICE_PRICE_PATH") or None,
            "apipoint_avgcarprice_param_map": _json_mapping("APIPOINT_AVGCARPRICE_PARAM_MAP"),
            "apipoint_carprices_url": os.getenv("APIPOINT_CARPRICES_URL") or None,
            "apipoint_carprices_price_path": os.getenv("APIPOINT_CARPRICES_PRICE_PATH") or None,
            "apipoint_carprices_param_map": _json_mapping("APIPOINT_CARPRICES_PARAM_MAP"),
            "apipoint_auth_header": os.getenv("APIPOINT_AUTH_HEADER") or None,
            "apipoint_auth_value": os.getenv("APIPOINT_AUTH_VALUE") or None,
            "apipoint_cache_ttl_seconds": _positive_int("APIPOINT_CACHE_TTL_SECONDS", 3_600),
            "apipoint_connect_timeout": _positive_float("APIPOINT_CONNECT_TIMEOUT", 5.0),
            "apipoint_read_timeout": _positive_float("APIPOINT_READ_TIMEOUT", 20.0),
            "quick_sale_coefficient": _decimal_between_zero_one("QUICK_SALE_COEFFICIENT", "0.92"),
            "fixed_expenses_rub": _nonnegative_int("FIXED_EXPENSES_RUB", 5_000),
            "risk_reserve_rub": _nonnegative_int("RISK_RESERVE_RUB", 10_000),
            "target_profit_rub": _nonnegative_int("TARGET_PROFIT_RUB", 40_000),
            "excellent_price_margin_rub": _nonnegative_int("EXCELLENT_PRICE_MARGIN_RUB", 10_000),
        }
        missing = [key for key in ("telegram_bot_token",) if not values[key]]
        if not values["owner_telegram_ids"]:
            missing.append("OWNER_TELEGRAM_IDS")
        if missing:
            raise RuntimeError(f"Не заданы обязательные переменные: {', '.join(missing)}")
        return cls(**values)


def _parse_owner_ids(raw: str) -> frozenset[int]:
    try:
        values = frozenset(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as error:
        raise RuntimeError("OWNER_TELEGRAM_IDS должен содержать Telegram ID через запятую") from error
    if any(value <= 0 for value in values):
        raise RuntimeError("OWNER_TELEGRAM_IDS должен содержать положительные ID")
    return values


def _json_mapping(name: str) -> dict[str, str] | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{name} должен быть JSON-объектом") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(item, str)
                                               for key, item in value.items()):
        raise RuntimeError(f"{name} должен сопоставлять строки со строками")
    return value


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
