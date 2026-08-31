from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()

YANDEX_MODEL_URI = "gpt://b1gmpvdiu7blj491i69q/yandexgpt-5.1/latest"


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    yandex_oauth_token: str
    yandex_folder_id: str
    database_url: str
    auto_ru_api_url: str | None = None
    auto_ru_api_token: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        values = {
            "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "yandex_oauth_token": os.getenv("YANDEX_CLOUD_OAUTH_TOKEN", ""),
            "yandex_folder_id": os.getenv("YANDEX_CLOUD_FOLDER_ID", ""),
            "database_url": os.getenv("DATABASE_URL", ""),
            "auto_ru_api_url": os.getenv("AUTO_RU_API_URL") or None,
            "auto_ru_api_token": os.getenv("AUTO_RU_API_TOKEN") or None,
        }
        missing = [key for key in list(values)[:4] if not values[key]]
        if missing:
            raise RuntimeError(f"Не заданы обязательные переменные: {', '.join(missing)}")
        return cls(**values)

