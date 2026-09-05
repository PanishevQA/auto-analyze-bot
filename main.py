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
from services.apipoint import APIpointClient, FakeAPIpointClient
from services.parts_orchestrator import PartsSearchOrchestrator, build_parts_provider
from schemas import PartCondition
from services.yandex_parts_agent import YandexPartsAgent
from services.deal_engine import DealEngine, DealSettings
from services.repair_catalog import RepairCatalog
from services.yandex_vision import YandexVisionClient
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
    repair_catalog = await RepairCatalog.load()
    deal_engine = DealEngine(DealSettings(
        quick_sale_coefficient=settings.quick_sale_coefficient,
        fixed_expenses_rub=settings.fixed_expenses_rub,
        risk_reserve_rub=settings.risk_reserve_rub,
        target_profit_rub=settings.target_profit_rub,
        excellent_price_margin_rub=settings.excellent_price_margin_rub,
    ))
    async with httpx.AsyncClient(timeout=timeout) as client:
        apipoint = FakeAPIpointClient(scenario=settings.test_apipoint_scenario,
            high_confidence_offers=settings.apipoint_high_confidence_offers,
            limited_confidence_offers=settings.apipoint_limited_confidence_offers) if settings.test_mode else APIpointClient(
            client, api_url=settings.apipoint_api_url, token=settings.apipoint_token,
            cache_ttl_seconds=settings.apipoint_cache_ttl_seconds,
            high_confidence_offers=settings.apipoint_high_confidence_offers,
            limited_confidence_offers=settings.apipoint_limited_confidence_offers,
        )
        if settings.test_mode:
            logger.warning("TEST MODE enabled: APIpoint network calls are disabled; Yandex AI and parts providers are unaffected")
        vision = YandexVisionClient(client, endpoint=settings.yandex_ai_endpoint,
            api_key=settings.yandex_ai_api_key, model_uri=settings.yandex_vision_model_uri,
            prompt_version=settings.yandex_vision_prompt_version,
            defect_codes=list(repair_catalog.items))
        vision.timeout = httpx.Timeout(connect=settings.yandex_vision_connect_timeout,
            read=settings.yandex_vision_read_timeout, write=settings.yandex_vision_read_timeout,
            pool=settings.yandex_vision_connect_timeout)
        vision.max_retries = settings.yandex_vision_max_retries
        parts_agent=YandexPartsAgent(vision,model_uri=settings.yandex_parts_model_uri,
            query_prompt_version=settings.yandex_parts_prompt_version,
            match_prompt_version=settings.yandex_parts_match_prompt_version,
            max_retries=settings.yandex_parts_max_retries)
        parts_provider=await build_parts_provider(settings,vision,parts_agent)
        parts_orchestrator=PartsSearchOrchestrator(parts_provider,
            default_condition=PartCondition(settings.parts_default_condition),agent=parts_agent)
        bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dispatcher = Dispatcher(
            db=db, apipoint=apipoint, deal_engine=deal_engine,
            repair_catalog=repair_catalog, vision=vision, settings=settings,
            parts_orchestrator=parts_orchestrator,
            parts_agent=parts_agent,
        )
        dispatcher.update.outer_middleware(OwnerAccessMiddleware(settings.owner_telegram_ids))
        dispatcher.include_router(build_router())
        try:
            identity = await bot.get_me()
            logger.info("Бот успешно запущен: @%s (id=%s)", identity.username, identity.id)
            logger.info("APIpoint endpoint configured=%s; vision mode=%s", bool(settings.apipoint_token),
                        "enabled" if settings.yandex_ai_api_key else "degraded")
            logger.info("APIpoint mode: %s", "TEST" if settings.test_mode else "LIVE")
            logger.info("Parts search mode: %s", settings.parts_search_mode)
            logger.info("Drom browser permission confirmed: %s", str(settings.drom_baza_permission_confirmed).lower())
            await dispatcher.start_polling(bot)
        finally:
            close=getattr(parts_provider,"close",None)
            if close: await close()
            await bot.session.close()
            await close_db()


if __name__ == "__main__":
    asyncio.run(main())
