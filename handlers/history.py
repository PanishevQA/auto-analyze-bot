import html
import logging
from dataclasses import replace
from datetime import datetime, timezone, timedelta

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram import F

from schemas import ConditionAssessment, MarketEstimate, RepairEstimate, VehicleSpec, PartPriceEstimate, PartsStatus
from services.repair_catalog import RepairCatalog
from services.deal_engine import DealEngine
from services.parts import mark_stale_quotes
from utils.deal_formatters import format_deal_details, format_deal_summary
from utils.validators import validate_price

from utils.formatters import money
from utils.messages import answer_long_html
from utils.keyboards import HISTORY,NEW_ANALYSIS,HOME,main_menu

router = Router()
logger=logging.getLogger(__name__)

class Recalculation(StatesGroup): waiting_price = State()


def _date(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M")


@router.message(Command("history"))
async def history(message: Message, command: CommandObject, db, settings, deal_engine, repair_catalog) -> None:
    argument = (command.args or "").strip()
    if argument:
        await show_calculation(message, argument, db, settings=settings,deal_engine=deal_engine,repair_catalog=repair_catalog)
        return
    await show_history_buttons(message,db)

@router.message(F.text==HISTORY)
async def history_button(message:Message,db): await show_history_buttons(message,db)

async def show_history_buttons(message:Message,db):
    calculations = await db.get_user_calculations_list(message.from_user.id)
    if not calculations:
        await message.answer("📭 У вас пока нет сохраненных расчетов.",reply_markup=main_menu())
        return
    keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=f"#{item['id']} {item['car_model']} {item['year']} — {item['created_at']:%d.%m}",callback_data=f"report:{item['id']}")]
        for item in calculations]+[[InlineKeyboardButton(text="🏠 Главное меню",callback_data="history:home")]])
    await message.answer("📋 <b>Ваши последние расчёты</b>",reply_markup=keyboard)

@router.callback_query(F.data.startswith("report:"))
async def report_button(callback:CallbackQuery,db,settings,deal_engine,repair_catalog):
    await show_calculation(callback.message,callback.data.split(":",1)[1],db,owner_id=callback.from_user.id,
        settings=settings,deal_engine=deal_engine,repair_catalog=repair_catalog)
    await callback.answer()

@router.callback_query(F.data=="history:home")
async def history_home(callback:CallbackQuery,state:FSMContext):
    await state.clear(); await callback.message.answer("Главное меню",reply_markup=main_menu()); await callback.answer()


async def show_calculation(message: Message, argument: str, db,owner_id:int|None=None,settings=None,
                           deal_engine=None,repair_catalog=None) -> None:
    try:
        calculation_id = int(argument)
        if calculation_id <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Укажите положительный ID: <code>/history 1</code>")
        return
    calculation = await db.get_calculation_by_id(calculation_id,owner_id or message.from_user.id)
    if calculation is None:
        await message.answer(
            f"❌ Расчет #{calculation_id} не найден или не принадлежит вам."
        )
        return
    heading = f"📊 <b>ОТЧЕТ #{calculation_id}</b> (от {_date(calculation['created_at'])})\n\n"
    quoted_at=calculation.get("parts_quoted_at"); report=calculation["final_report"]
    if quoted_at:
        if quoted_at.tzinfo is None: quoted_at=quoted_at.replace(tzinfo=timezone.utc)
        age=datetime.now(timezone.utc)-quoted_at
        heading += f"Цены запчастей получены: {_date(quoted_at)} (возраст {int(age.total_seconds()//3600)} ч.)\n"
        if settings and age.total_seconds()>settings.parts_price_cache_ttl_hours*3600:
            heading += "⚠️ <b>Цены запчастей устарели</b>\nОкончательная экономика требует обновления.\n"
        heading += "\n"
    if settings and deal_engine and repair_catalog:
        try:
            vehicle=VehicleSpec.model_validate(calculation["car_data"])
            market_data=calculation.get("market_data") or {}
            market=MarketEstimate.model_validate(market_data) if market_data.get("source") else None
            repairs=RepairEstimate.model_validate(calculation["repair_estimate"])
            condition=ConditionAssessment.model_validate(calculation["condition_data"])
            parts=[PartPriceEstimate.model_validate(item) for item in (calculation.get("parts_data") or [])]
            parts=mark_stale_quotes(parts,now=datetime.now(timezone.utc),
                ttl=timedelta(hours=settings.parts_price_cache_ttl_hours))
            complete=all(item.status in {PartsStatus.READY,PartsStatus.NOT_REQUIRED} for item in parts)
            total=sum(item.selected_price_rub or 0 for item in parts if item.status is PartsStatus.READY)
            user=await db.get_user(owner_id or message.from_user.id)
            active_engine=deal_engine
            if user and user.target_profit_rub is not None:
                active_engine=DealEngine(replace(deal_engine.settings,target_profit_rub=user.target_profit_rub))
            deal=active_engine.calculate(asking_price_rub=vehicle.asking_price_rub,market=market,repairs=repairs,
                coverage=condition.coverage,has_blocking_risk=repair_catalog.has_blocking_risk(condition.defects),
                parts_total_rub=total,parts_complete=complete)
            report=format_deal_summary(vehicle,deal,market)+"\n\n"+format_deal_details(vehicle,market,condition,repairs,deal,parts)
        except Exception as error:
            logger.warning("Structured history rebuild failed calculation_id=%s error=%s",
                           calculation_id,type(error).__name__)
    rows=[[InlineKeyboardButton(text="🔄 Пересчитать с другой ценой",callback_data=f"recalc:{calculation_id}")]]
    if calculation.get("parts_data"): rows.append([InlineKeyboardButton(text="🔄 Обновить цены запчастей",callback_data=f"manualparts:{calculation_id}")])
    rows.extend([[InlineKeyboardButton(text="📋 К истории",callback_data="history:list"),InlineKeyboardButton(text="🚗 Новый анализ",callback_data="analyze")],
        [InlineKeyboardButton(text="🏠 Главное меню",callback_data="history:home")]])
    keyboard=InlineKeyboardMarkup(inline_keyboard=rows)
    await answer_long_html(message, heading + report)
    await message.answer("Действия с расчётом:",reply_markup=keyboard)

@router.callback_query(F.data=="history:list")
async def history_list_callback(callback:CallbackQuery,db):
    await show_history_buttons(callback.message,db); await callback.answer()

@router.callback_query(F.data.startswith("recalc:"))
async def recalc_begin(callback:CallbackQuery,state:FSMContext,db):
    calc_id=int(callback.data.split(":",1)[1]); calculation=await db.get_calculation_by_id(calc_id,callback.from_user.id)
    if not calculation: await callback.answer("Расчёт не найден",show_alert=True); return
    await state.set_state(Recalculation.waiting_price); await state.update_data(parent_calculation_id=calc_id)
    await callback.message.answer("Введите новую цену покупки, ₽:"); await callback.answer()

@router.message(Recalculation.waiting_price)
async def recalc_price(message:Message,state:FSMContext,db,deal_engine:DealEngine,repair_catalog:RepairCatalog,settings):
    try: new_price=validate_price(message.text or "")
    except ValueError as error: await message.answer(f"❌ {error}"); return
    data=await state.get_data(); old=await db.get_calculation_by_id(data["parent_calculation_id"],message.from_user.id)
    try:
        vehicle=VehicleSpec.model_validate(old["car_data"]).model_copy(update={"asking_price_rub":new_price})
        market=MarketEstimate.model_validate(old["market_data"]) if old["market_data"].get("source") else None
        repairs=RepairEstimate.model_validate(old["repair_estimate"])
        condition=ConditionAssessment.model_validate(old["condition_data"])
        parts=[PartPriceEstimate.model_validate(item) for item in (old.get("parts_data") or [])]
        parts=mark_stale_quotes(parts,now=datetime.now(timezone.utc),ttl=timedelta(hours=settings.parts_price_cache_ttl_hours))
    except Exception:
        await message.answer("Этот расчёт создан в старой версии бота и не содержит данных о состоянии автомобиля. Выполните новый анализ."); await state.clear(); return
    blocking=repair_catalog.has_blocking_risk(condition.defects)
    parts_complete=all(item.status in {PartsStatus.READY,PartsStatus.NOT_REQUIRED} for item in parts)
    parts_total=sum(item.selected_price_rub or 0 for item in parts if item.status is PartsStatus.READY)
    deal=deal_engine.calculate(asking_price_rub=new_price,market=market,repairs=repairs,
        coverage=condition.coverage,has_blocking_risk=blocking,parts_total_rub=parts_total,
        parts_complete=parts_complete)
    summary=format_deal_summary(vehicle,deal,market); details=format_deal_details(vehicle,market,condition,repairs,deal,parts)
    await db.save_calculation(message.from_user.id,car_data=vehicle.model_dump(mode="json"),
        market_data=market.model_dump(mode="json") if market else {},repair_estimate=repairs.model_dump(mode="json"),
        scores={"deal_result":deal.model_dump(mode="json")},final_report=summary+"\n\n"+details,
        metadata={"parent_calculation_id":old["id"],"status":"COMPLETED","condition_data":condition.model_dump(mode="json"),
            "parts_data":[p.model_dump(mode="json") for p in parts],"parts_status":old.get("parts_status"),
            "parts_quoted_at":old.get("parts_quoted_at"),"parts_provider":old.get("parts_provider"),
            "test_mode":old.get("test_mode"),"market_status":old.get("market_status"),
            "vision_status":old.get("vision_status"),"parts_search_mode":old.get("parts_search_mode"),
            "parts_source":old.get("parts_source"),"parts_complete":parts_complete,
            "parts_query_data":old.get("parts_query_data"),
            "parts_permission_confirmed":old.get("parts_permission_confirmed"),
            "parts_prompt_version":old.get("parts_prompt_version"),**old.get("versions",{})})
    await state.clear(); await message.answer(summary); await answer_long_html(message,details)
