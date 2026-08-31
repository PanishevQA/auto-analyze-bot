import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Settings
from database.models import close_db, init_db
from database.queries import Database
from handlers import build_router
from services.market_api import MarketService
from services.yandex_gpt import YandexGPTService

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = Settings.from_env()
    await init_db()
    db = Database()
    async with aiohttp.ClientSession() as session:
        gpt = YandexGPTService(
            settings.yandex_folder_id,
            session,
            api_key=settings.yandex_api_key,
            oauth_token=settings.yandex_oauth_token,
        )
        market = MarketService(session, settings.auto_ru_api_url, settings.auto_ru_api_token)
        bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dispatcher = Dispatcher(db=db, gpt=gpt, market=market)
        dispatcher.include_router(build_router())
        try:
            identity = await bot.get_me()
            logger.info("Бот успешно запущен: @%s (id=%s)", identity.username, identity.id)
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()
            await close_db()


if __name__ == "__main__":
    asyncio.run(main())
