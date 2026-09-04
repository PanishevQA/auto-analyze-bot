import asyncio
from contextlib import suppress
from decimal import Decimal
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery,InlineKeyboardButton,InlineKeyboardMarkup

from handlers.questionnaire import Questionnaire
from schemas import (AnalysisStatus, ConditionAssessment, Coverage, MarketEstimate,
                     PhotoReference, RepairEstimate, SourceMode, VehicleSpec)
from services.apipoint import APIpointError
from services.deal_engine import DealEngine
from services.repair_catalog import RepairCatalog
from services.photos import temporary_analysis_directory
from services.parts_orchestrator import PartsSearchOrchestrator
from schemas import PartsStatus
from utils.deal_formatters import format_deal_details, format_deal_summary
from utils.messages import answer_long_html

router = Router()


@router.callback_query(Questionnaire.confirmation, F.data.startswith("confirm:"))
async def analyze(callback: CallbackQuery, state: FSMContext, db, apipoint, vision,
                  deal_engine: DealEngine, repair_catalog: RepairCatalog, parts_orchestrator: PartsSearchOrchestrator,
                  settings) -> None:
    request_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if request_id != data.get("analysis_request_id"):
        await callback.answer("Устаревшее подтверждение", show_alert=True); return
    vehicle = vehicle_from_fsm(data)
    idempotency_key = f"{callback.from_user.id}:{request_id}"
    calculation_id, created = await db.reserve_analysis(callback.from_user.id, idempotency_key,
                                                         request_id, vehicle.model_dump(mode="json"))
    if not created:
        existing = await db.get_by_idempotency_key(idempotency_key, callback.from_user.id)
        await callback.answer("Запрос уже принят")
        if existing and existing.get("final_report"): await answer_long_html(callback.message, existing["final_report"])
        else: await callback.message.answer("⏳ Анализ уже выполняется.")
        return
    await callback.answer(); await callback.message.answer("⏳ Анализ запущен: рынок и фотографии обрабатываются...")
    heartbeat = asyncio.create_task(_heartbeat(callback.message))
    photos = [PhotoReference.model_validate(item) for item in data.get("photos", [])]
    try:
        async with temporary_analysis_directory(calculation_id) as temp_dir:
            market_task = asyncio.create_task(_market(apipoint, vehicle, request_id))
            try:
                paths = await download_photos(callback.bot, photos, temp_dir)
                if len(photos) < settings.min_photos_for_vision:
                    async def insufficient_photos():
                        return vision.unavailable("Недостаточно фотографий для vision-анализа")
                    vision_task = asyncio.create_task(insufficient_photos())
                else:
                    vision_task = asyncio.create_task(vision.assess(vehicle, photos, paths, request_id))
                market, condition = await asyncio.gather(market_task, vision_task)
            except Exception:
                market = await market_task
                condition = vision.unavailable("Фотографии не удалось скачать или обработать")
            repairs = repair_catalog.estimate(condition.defects, vehicle.region)
            blocking = repair_catalog.has_blocking_risk(condition.defects)
            part_quotes=await parts_orchestrator.estimate(vehicle,condition.defects,repairs)
            parts_total=sum(q.selected_price_rub or 0 for q in part_quotes if q.status is PartsStatus.READY)
            parts_complete=all(q.status in {PartsStatus.READY,PartsStatus.NOT_REQUIRED} for q in part_quotes)
            overall_parts_status=(PartsStatus.NOT_REQUIRED if not part_quotes else PartsStatus.READY
                if parts_complete else next(q.status for q in part_quotes if q.status not in {PartsStatus.READY,PartsStatus.NOT_REQUIRED}))
            deal = deal_engine.calculate(asking_price_rub=vehicle.asking_price_rub, market=market,
                repairs=repairs, coverage=condition.coverage, has_blocking_risk=blocking,
                parts_total_rub=parts_total, parts_complete=parts_complete)
            summary = format_deal_summary(vehicle, deal, market)
            details = format_deal_details(vehicle, market, condition, repairs, deal, part_quotes)
            market_status = AnalysisStatus.OK if market else AnalysisStatus.UNAVAILABLE
            vision_status = (AnalysisStatus.OK if condition.coverage is Coverage.FULL else
                             AnalysisStatus.LIMITED if condition.coverage is Coverage.LIMITED else AnalysisStatus.UNAVAILABLE)
            status = "COMPLETED" if market_status is AnalysisStatus.OK and vision_status is AnalysisStatus.OK else "PARTIAL"
            if not parts_complete: status="PARTIAL"
            await db.complete_analysis(calculation_id, car_data=vehicle.model_dump(mode="json"),
                market_data=market.model_dump(mode="json") if market else {}, repair_estimate=repairs.model_dump(mode="json"),
                scores={"deal_result":deal.model_dump(mode="json")}, final_report=summary+"\n\n"+details,
                status=status, photos_metadata=[p.model_dump(mode="json",exclude={"local_temp_path"}) for p in photos],
                condition_data=condition.model_dump(mode="json"),
                source_url=str(vehicle.source_url) if vehicle.source_url else None, source_mode=vehicle.source_mode.value,
                market_status=market_status.value, vision_status=vision_status.value, model_uri=condition.model_uri,
                prompt_version=condition.prompt_version, adapter_version=market.adapter_version if market else None,
                catalog_version=repairs.catalog_version, formula_version=deal.formula_version,
                test_mode=bool(market and market.is_test_data),
                parts_data=[q.model_dump(mode="json") for q in part_quotes],
                parts_status=overall_parts_status.value,
                parts_quoted_at=next((q.fetched_at for q in part_quotes if q.fetched_at), None),
                parts_provider=next((q.provider for q in part_quotes if q.provider), None),
                parts_search_mode=settings.parts_search_mode,parts_source=next((q.provider for q in part_quotes if q.provider),None),
                parts_complete=parts_complete,parts_query_data=[q.query_data for q in part_quotes],
                parts_permission_confirmed=settings.drom_baza_permission_confirmed,
                parts_prompt_version=settings.yandex_parts_prompt_version)
            await state.clear(); await callback.message.answer(summary); await answer_long_html(callback.message, details)
            if settings.parts_search_mode=="MANUAL_BROWSER" and part_quotes and not parts_complete:
                await callback.message.answer("Можно добавить скриншоты выдачи для расчёта запчастей.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                        text="📷 Добавить объявления",callback_data=f"manualparts:{calculation_id}")]]))
    except Exception:
        await db.complete_analysis(calculation_id, status="FAILED")
        await callback.message.answer("❌ Анализ завершился ошибкой. Временные файлы удалены.")
        return
    finally:
        heartbeat.cancel();
        with suppress(asyncio.CancelledError): await heartbeat


async def _market(client, vehicle, request_id) -> MarketEstimate | None:
    try: return await client.estimate(vehicle, request_id)
    except APIpointError: return None


async def _heartbeat(message) -> None:
    while True:
        await asyncio.sleep(25); await message.answer("⏳ Анализ продолжается...")


async def download_photos(bot, photos: list[PhotoReference], directory: Path) -> list[Path]:
    paths=[]
    for photo in photos:
        remote=await bot.get_file(photo.telegram_file_id)
        suffix={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}[photo.mime_type]
        path=directory/f"{photo.order_number:02d}{suffix}"
        await bot.download_file(remote.file_path,destination=path); paths.append(path)
    return paths


def vehicle_from_fsm(data: dict) -> VehicleSpec:
    return VehicleSpec(source_url=data.get("source_url"), source_mode=SourceMode.MANUAL,
        make=data["make"], model=data["model"], year=int(data["year"]), generation=data.get("generation"),
        mileage_km=int(data["mileage_km"]), asking_price_rub=int(data["asking_price_rub"]),
        region=data["region"], engine_volume_l=Decimal(data["engine_volume_l"]) if data.get("engine_volume_l") else None,
        fuel_type=data.get("fuel_type"), horsepower=data.get("horsepower"), transmission=data.get("transmission"),
        drive=data.get("drive"), body_type=data.get("body_type"), seller_description=data.get("seller_description"),
        vin=data.get("vin"))
