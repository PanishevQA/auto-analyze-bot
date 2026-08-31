import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from handlers.questionnaire import Questionnaire
from services.calculator import (calculate_profit, calculate_profitability_score,
                                 calculate_total_costs)
from utils.formatters import format_report

router = Router()


@router.callback_query(Questionnaire.waiting_confirmation, F.data == "confirm")
async def analyze(callback: CallbackQuery, state: FSMContext, db, gpt, market) -> None:
    await callback.answer()
    await callback.message.answer("⏳ Анализирую рынок и составляю смету... Это может занять некоторое время.")
    data = await state.get_data()
    user = await db.get_user(callback.from_user.id)
    if user is None:
        await callback.message.answer("Пользователь не найден. Нажмите /start.")
        return
    data["region"] = user.region
    try:
        market_data = await market.prices(data["car_model"], data["year"], data["region"])
        repair = await gpt.from_template("repair_estimate.txt", data, {"repair_items": []})
        risk = await gpt.from_template("risk_assessment.txt", data, {
            "risk_score": 0, "risk_explanation": "Не удалось получить оценку.",
            "inspection_checklist": [],
        })
    except asyncio.TimeoutError:
        await callback.message.answer("Превышено время ожидания. Попробуйте позже.")
        return
    items = sanitize_items(repair.get("repair_items", []))
    risk = sanitize_risk(risk)
    economy = sum(item["budget_economy"] for item in items)
    optimal = sum(item["budget_optimal"] for item in items)
    total = calculate_total_costs(data["price"], optimal)
    profit = calculate_profit(data["price"], optimal, market_data["quick"])
    scores = {"economy_total": economy, "optimal_total": optimal, "total_costs": total,
              "profit": profit, "profitability": calculate_profitability_score(profit, total)}
    report = format_report(data, market_data, items, risk, scores)
    await db.save_calculation(callback.from_user.id, car_data=data, market_data=market_data,
                              repair_estimate={"repair_items": items}, scores={**scores, **risk},
                              final_report=report)
    await state.clear()
    await callback.message.answer(report, disable_web_page_preview=True)


def sanitize_items(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    result = []
    for raw in value:
        if not isinstance(raw, dict) or raw.get("category") not in {"critical", "appearance", "maintenance"}:
            continue
        try:
            economy, optimal = max(0, int(raw["budget_economy"])), max(0, int(raw["budget_optimal"]))
        except (KeyError, TypeError, ValueError):
            continue
        result.append({"category": raw["category"], "item": str(raw.get("item", "Работа")),
                       "budget_economy": economy, "budget_optimal": optimal,
                       "search_query": str(raw.get("search_query", raw.get("item", "автозапчасть")))})
    return result


def sanitize_risk(value) -> dict:
    try:
        score = max(0, min(100, int(value.get("risk_score", 0))))
    except (AttributeError, TypeError, ValueError):
        score = 0
    if not isinstance(value, dict):
        value = {}
    checklist = value.get("inspection_checklist", [])
    return {"risk_score": score, "risk_explanation": str(value.get("risk_explanation", "Нет данных"))[:150],
            "inspection_checklist": [str(x) for x in checklist[:7]] if isinstance(checklist, list) else []}
