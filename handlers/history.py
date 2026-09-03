import html

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram import F

from schemas import ConditionAssessment, MarketEstimate, RepairEstimate, VehicleSpec, PartPriceEstimate, PartsStatus
from services.repair_catalog import RepairCatalog
from services.deal_engine import DealEngine
from utils.deal_formatters import format_deal_details, format_deal_summary
from utils.validators import validate_price

from utils.formatters import money
from utils.messages import answer_long_html

router = Router()

class Recalculation(StatesGroup): waiting_price = State()


def _date(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M")


@router.message(Command("history"))
async def history(message: Message, command: CommandObject, db) -> None:
    argument = (command.args or "").strip()
    if argument:
        await show_calculation(message, argument, db)
        return
    calculations = await db.get_user_calculations_list(message.from_user.id)
    if not calculations:
        await message.answer("📭 У вас пока нет сохраненных расчетов.")
        return
    rows = ["📋 <b>Ваши последние расчеты:</b>"]
    for item in calculations:
        rows.append(
            f"<b>#{item['id']}</b> — {html.escape(str(item['car_model']))} ({item['year']})\n"
            f"🛣 Пробег: {money(int(item['mileage']))} км\n📅 Дата: {_date(item['created_at'])}"
        )
    rows.append("💡 Для просмотра отчета используйте:\n<code>/history &lt;ID&gt;</code>\n"
                "Например: <code>/history 1</code>")
    await message.answer("\n\n".join(rows))


async def show_calculation(message: Message, argument: str, db) -> None:
    try:
        calculation_id = int(argument)
        if calculation_id <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Укажите положительный ID: <code>/history 1</code>")
        return
    calculation = await db.get_calculation_by_id(calculation_id, message.from_user.id)
    if calculation is None:
        await message.answer(
            f"❌ Расчет #{calculation_id} не найден или не принадлежит вам."
        )
        return
    heading = f"📊 <b>ОТЧЕТ #{calculation_id}</b> (от {_date(calculation['created_at'])})\n\n"
    keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="🔄 Пересчитать с другой ценой",callback_data=f"recalc:{calculation_id}")]])
    await answer_long_html(message, heading + calculation["final_report"])
    await message.answer("Действия с расчётом:",reply_markup=keyboard)

@router.callback_query(F.data.startswith("recalc:"))
async def recalc_begin(callback:CallbackQuery,state:FSMContext,db):
    calc_id=int(callback.data.split(":",1)[1]); calculation=await db.get_calculation_by_id(calc_id,callback.from_user.id)
    if not calculation: await callback.answer("Расчёт не найден",show_alert=True); return
    await state.set_state(Recalculation.waiting_price); await state.update_data(parent_calculation_id=calc_id)
    await callback.message.answer("Введите новую цену покупки, ₽:"); await callback.answer()

@router.message(Recalculation.waiting_price)
async def recalc_price(message:Message,state:FSMContext,db,deal_engine:DealEngine,repair_catalog:RepairCatalog):
    try: new_price=validate_price(message.text or "")
    except ValueError as error: await message.answer(f"❌ {error}"); return
    data=await state.get_data(); old=await db.get_calculation_by_id(data["parent_calculation_id"],message.from_user.id)
    try:
        vehicle=VehicleSpec.model_validate(old["car_data"]).model_copy(update={"asking_price_rub":new_price})
        market=MarketEstimate.model_validate(old["market_data"]) if old["market_data"].get("source") else None
        repairs=RepairEstimate.model_validate(old["repair_estimate"])
        condition=ConditionAssessment.model_validate(old["condition_data"])
        parts=[PartPriceEstimate.model_validate(item) for item in (old.get("parts_data") or [])]
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
            "vision_status":old.get("vision_status"),**old.get("versions",{})})
    await state.clear(); await message.answer(summary); await answer_long_html(message,details)
