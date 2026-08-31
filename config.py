from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'bot_database.db'}"
YANDEXGPT_ENDPOINT = os.getenv(
    "YANDEXGPT_ENDPOINT", "https://ai.api.cloud.yandex.net/v1/chat/completions"
)
YANDEXGPT_MODEL_URI = os.getenv(
    "YANDEXGPT_MODEL_URI",
    "gpt://b1gmpvdiu7blj491i69q/yandexgpt-5.1/latest",
)
YANDEX_GPT_CONFIG = {
    "endpoint": YANDEXGPT_ENDPOINT,
    "model_uri": YANDEXGPT_MODEL_URI,
    "temperature": 0.3,
    "max_tokens": 2000,
    "timeout": 60,
}


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    yandex_folder_id: str
    yandex_api_key: str | None = None
    yandex_oauth_token: str | None = None
    auto_ru_api_url: str | None = None
    auto_ru_api_token: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        values = {
            "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "yandex_folder_id": os.getenv("YANDEX_CLOUD_FOLDER_ID", ""),
            "yandex_api_key": os.getenv("YANDEX_CLOUD_API_KEY") or None,
            "yandex_oauth_token": os.getenv("YANDEX_CLOUD_OAUTH_TOKEN") or None,
            "auto_ru_api_url": os.getenv("AUTO_RU_API_URL") or None,
            "auto_ru_api_token": os.getenv("AUTO_RU_API_TOKEN") or None,
        }
        missing = [key for key in ("telegram_bot_token", "yandex_folder_id") if not values[key]]
        if not values["yandex_api_key"] and not values["yandex_oauth_token"]:
            missing.append("YANDEX_CLOUD_API_KEY или YANDEX_CLOUD_OAUTH_TOKEN")
        if missing:
            raise RuntimeError(f"Не заданы обязательные переменные: {', '.join(missing)}")
        return cls(**values)
