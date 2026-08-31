import asyncio

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Settings
from database.queries import Database
from handlers import build_router
from services.market_api import MarketService
from services.yandex_gpt import YandexGPTService


async def main() -> None:
    settings = Settings.from_env()
    db = Database(settings.database_url)
    await db.connect()
    await db.init_schema()
    async with aiohttp.ClientSession() as session:
        gpt = YandexGPTService(settings.yandex_oauth_token, settings.yandex_folder_id, db, session)
        market = MarketService(session, settings.auto_ru_api_url, settings.auto_ru_api_token)
        bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dispatcher = Dispatcher(db=db, gpt=gpt, market=market)
        dispatcher.include_router(build_router())
        try:
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())

