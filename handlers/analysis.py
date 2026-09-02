from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from handlers.questionnaire import Questionnaire
from schemas import (ConditionAssessment, Coverage, MarketEstimate,
                     RepairEstimate, SourceMode, VehicleSpec)
from services.apipoint import APIpointError
from services.deal_engine import DealEngine
from services.repair_catalog import RepairCatalog
from utils.deal_formatters import format_deal_details, format_deal_summary
from utils.messages import answer_long_html

router = Router()


@router.callback_query(Questionnaire.waiting_confirmation, F.data == "confirm")
async def analyze(
    callback: CallbackQuery, state: FSMContext, db, apipoint, deal_engine: DealEngine,
    repair_catalog: RepairCatalog,
) -> None:
    await callback.answer()
    await callback.message.answer("⏳ Получаю рыночную оценку APIpoint...")
    data = await state.get_data()
    user = await db.get_user(callback.from_user.id)
    if user is None:
        await callback.message.answer("Пользователь не найден. Нажмите /start.")
        return
    try:
        vehicle = vehicle_from_fsm(data, user.region)
    except (ValueError, InvalidOperation) as error:
        await callback.message.answer(f"Некорректные данные автомобиля: {error}")
        return

    market: MarketEstimate | None
    try:
        market = await apipoint.estimate(vehicle)
    except APIpointError:
        market = None
    condition = ConditionAssessment(
        coverage=Coverage.UNAVAILABLE, defects=[],
        limitations=["Фотографии не анализировались: модуль vision относится к этапу P1"],
        inspection_checklist=[], model_uri="not-used-p0", prompt_version="not-used-p0",
    )
    repairs = repair_catalog.estimate(condition.defects, vehicle.region)
    deal = deal_engine.calculate(
        asking_price_rub=vehicle.asking_price_rub, market=market,
        repairs=repairs, coverage=condition.coverage,
    )
    summary = format_deal_summary(vehicle, deal)
    details = format_deal_details(vehicle, market, condition, repairs, deal)
    await db.save_calculation(
        callback.from_user.id, car_data=vehicle.model_dump(mode="json"),
        market_data=market.model_dump(mode="json") if market else {"status": "UNAVAILABLE"},
        repair_estimate=repairs.model_dump(mode="json"),
        scores={"deal_result": deal.model_dump(mode="json"),
                "condition": condition.model_dump(mode="json")},
        final_report=summary + "\n\n" + details,
    )
    await state.clear()
    await callback.message.answer(summary)
    await answer_long_html(callback.message, details)


def vehicle_from_fsm(data: dict, region: str) -> VehicleSpec:
    model_text = str(data["car_model"]).strip().split(maxsplit=1)
    make = model_text[0]
    model = model_text[1] if len(model_text) > 1 else model_text[0]
    engine_text = str(data.get("engine", "")).strip()
    volume = None
    for token in engine_text.replace(",", ".").split():
        try:
            candidate = Decimal(token)
        except InvalidOperation:
            continue
        if Decimal("0") < candidate <= Decimal("20"):
            volume = candidate
            break
    return VehicleSpec(
        source_mode=SourceMode.MANUAL, make=make, model=model,
        year=int(data["year"]), mileage_km=int(data["mileage"]),
        asking_price_rub=int(data["price"]), region=region,
        engine_volume_l=volume, transmission=engine_text or None,
        seller_description=str(data.get("listing_description") or "") or None,
    )
