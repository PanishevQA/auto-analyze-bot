import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Settings
from database.models import close_db, init_db
from database.queries import Database
from handlers import build_router
from schemas import MarketSource
from services.apipoint import APIpointClient, EndpointAdapter
from services.deal_engine import DealEngine, DealSettings
from services.repair_catalog import RepairCatalog
from utils.access import OwnerAccessMiddleware

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = Settings.from_env()
    await init_db()
    db = Database()
    timeout = httpx.Timeout(
        connect=settings.apipoint_connect_timeout,
        read=settings.apipoint_read_timeout,
        write=settings.apipoint_read_timeout,
        pool=settings.apipoint_connect_timeout,
    )
    adapters = build_apipoint_adapters(settings)
    repair_catalog = await RepairCatalog.load()
    deal_engine = DealEngine(DealSettings(
        quick_sale_coefficient=settings.quick_sale_coefficient,
        fixed_expenses_rub=settings.fixed_expenses_rub,
        risk_reserve_rub=settings.risk_reserve_rub,
        target_profit_rub=settings.target_profit_rub,
        excellent_price_margin_rub=settings.excellent_price_margin_rub,
    ))
    async with httpx.AsyncClient(timeout=timeout) as client:
        apipoint = APIpointClient(
            client, adapters, auth_header=settings.apipoint_auth_header,
            auth_value=settings.apipoint_auth_value,
            cache_ttl_seconds=settings.apipoint_cache_ttl_seconds,
        )
        bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dispatcher = Dispatcher(
            db=db, apipoint=apipoint, deal_engine=deal_engine,
            repair_catalog=repair_catalog,
        )
        dispatcher.update.outer_middleware(OwnerAccessMiddleware(settings.owner_telegram_ids))
        dispatcher.include_router(build_router())
        try:
            identity = await bot.get_me()
            logger.info("Бот успешно запущен: @%s (id=%s)", identity.username, identity.id)
            logger.info("APIpoint adapters: %s", [adapter.alias for adapter in adapters] or ["not-configured"])
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()
            await close_db()


def build_apipoint_adapters(settings: Settings) -> list[EndpointAdapter]:
    adapters = []
    configurations = (
        ("Avgcarprice", MarketSource.APIPOINT_AVGCARPRICE,
         settings.apipoint_avgcarprice_url, settings.apipoint_avgcarprice_price_path,
         settings.apipoint_avgcarprice_param_map),
        ("Carprices", MarketSource.APIPOINT_CARPRICES,
         settings.apipoint_carprices_url, settings.apipoint_carprices_price_path,
         settings.apipoint_carprices_param_map),
    )
    for alias, source, url, price_path, parameter_map in configurations:
        if url and price_path and parameter_map:
            adapters.append(EndpointAdapter(alias, source, url, price_path, parameter_map))
    return adapters


if __name__ == "__main__":
    asyncio.run(main())
