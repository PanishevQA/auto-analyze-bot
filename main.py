import asyncio

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


async def main() -> None:
    settings = Settings.from_env()
    await init_db()
    db = Database()
    async with aiohttp.ClientSession() as session:
        gpt = YandexGPTService(settings.yandex_oauth_token, settings.yandex_folder_id, session)
        market = MarketService(session, settings.auto_ru_api_url, settings.auto_ru_api_token)
        bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dispatcher = Dispatcher(db=db, gpt=gpt, market=market)
        dispatcher.include_router(build_router())
        try:
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()
            await close_db()


if __name__ == "__main__":
    asyncio.run(main())
