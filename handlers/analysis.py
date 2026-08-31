import asyncio
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from handlers.questionnaire import Questionnaire
from services.yandex_gpt import YandexGPTError
from utils.formatters import format_commercial_report
from utils.messages import answer_long_html

router = Router()
REPAIR_GROUPS = ("critical_repairs", "sale_preparation", "maintenance", "potential_repairs")


@router.callback_query(Questionnaire.waiting_confirmation, F.data == "confirm")
async def analyze(callback: CallbackQuery, state: FSMContext, db, gpt, market=None) -> None:
    await callback.answer()
    await callback.message.answer(
        "⏳ Выполняю коммерческий анализ автомобиля для перепродажи..."
    )
    data = await state.get_data()
    user = await db.get_user(callback.from_user.id)
    if user is None:
        await callback.message.answer("Пользователь не найден. Нажмите /start.")
        return
    prompt_data = {
        **data,
        "region": user.region,
        "purchase_price": data["price"],
        "additional_info": data["user_issues"],
    }
    try:
        raw = await gpt.from_template("full_analysis.txt", prompt_data, {}, strict=True)
        analysis = normalize_analysis(raw, prompt_data)
    except asyncio.TimeoutError:
        await callback.message.answer("Превышено время ожидания. Попробуйте позже.")
        return
    except (YandexGPTError, ValueError, TypeError, KeyError):
        await callback.message.answer(
            "Не удалось получить корректный коммерческий анализ от YandexGPT. "
            "Проверьте настройки API и повторите попытку."
        )
        return

    report = format_commercial_report(analysis)
    await db.save_calculation(
        callback.from_user.id,
        car_data=prompt_data,
        market_data=analysis["market"],
        repair_estimate=analysis["repairs"],
        scores={
            "economics": analysis["economics"],
            "risk": analysis["risk"],
            "liquidity": analysis["liquidity"],
            "negotiation": analysis["negotiation"],
            "verdict": analysis["verdict"],
        },
        final_report=report,
    )
    await state.clear()
    await answer_long_html(callback.message, report)


def _integer(value: Any, *, minimum: int | None = None, maximum: int | None = None) -> int:
    number = int(value)
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _text(value: Any, limit: int = 1_000) -> str:
    return str(value or "").strip()[:limit]


def _text_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item, 500) for item in value[:limit] if _text(item, 500)]


def _repair_items(value: Any, group: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for raw in value[:20]:
        if not isinstance(raw, dict):
            continue
        try:
            parts = _integer(raw.get("parts_cost", 0), minimum=0)
            labor = _integer(raw.get("labor_cost", 0), minimum=0)
        except (TypeError, ValueError):
            continue
        status = raw.get("status")
        if status not in {"confirmed", "potential"}:
            status = "potential" if group == "potential_repairs" else "confirmed"
        priority = raw.get("priority")
        if priority not in {"critical", "recommended", "optional"}:
            priority = "recommended"
        result.append({
            "name": _text(raw.get("name") or "Работа", 200),
            "reason": _text(raw.get("reason"), 500),
            "status": status,
            "parts_cost": parts,
            "labor_cost": labor,
            # Значению total_cost модели не доверяем: сумма всегда считается Python.
            "total_cost": parts + labor,
            "priority": priority,
        })
    return result


def normalize_analysis(raw: dict[str, Any], car: dict[str, Any]) -> dict[str, Any]:
    """Проверяет структуру ИИ и заново выполняет всю финансовую математику в Python."""
    if not isinstance(raw, dict):
        raise ValueError("Ожидался объект анализа")
    market_raw = raw.get("market")
    repairs_raw = raw.get("repairs")
    if not isinstance(market_raw, dict) or not isinstance(repairs_raw, dict):
        raise ValueError("Нет обязательных секций market/repairs")

    def market_range(name: str) -> dict[str, int]:
        value = market_raw.get(name, {})
        low = _integer(value.get("low", 0), minimum=0)
        mid = _integer(value.get("mid", 0), minimum=0)
        high = _integer(value.get("high", 0), minimum=0)
        if not low <= mid <= high or low == 0:
            raise ValueError(f"Некорректный диапазон рынка: {name}")
        return {"low": low, "mid": mid, "high": high}

    market = {"region": market_range("region"), "rf": market_range("rf")}
    realistic = _integer(market_raw.get("realistic_sale_price", 0), minimum=0)
    quick = min(_integer(market_raw.get("quick_sale_price", 0), minimum=0), realistic)
    if realistic == 0 or quick == 0:
        raise ValueError("Не получены цены продажи")
    market.update({"realistic_sale_price": realistic, "quick_sale_price": quick,
                   "market_comment": _text(market_raw.get("market_comment"), 1_000)})

    repairs = {group: _repair_items(repairs_raw.get(group), group) for group in REPAIR_GROUPS}
    minimum = sum(item["total_cost"] for item in repairs["critical_repairs"]
                  if item["status"] == "confirmed")
    recommended = minimum + sum(
        item["total_cost"] for group in ("sale_preparation", "maintenance")
        for item in repairs[group] if item["status"] == "confirmed"
    )
    risk_reserve = _integer(repairs_raw.get("risk_reserve", 0), minimum=0)
    repairs.update({"minimum_preparation_cost": minimum,
                    "recommended_preparation_cost": recommended,
                    "risk_reserve": risk_reserve})

    purchase = _integer(car["purchase_price"], minimum=0)
    total = purchase + recommended
    expected = realistic - total
    quick_profit = quick - total
    roi = round(expected / total * 100, 1) if total else 0.0
    economics_raw = raw.get("economics", {})
    break_even = realistic - recommended
    target = _integer(economics_raw.get("target_purchase_price", break_even), minimum=0,
                      maximum=max(0, break_even))
    excellent = _integer(economics_raw.get("excellent_purchase_price", target), minimum=0,
                         maximum=target)
    economics = {
        "purchase_price": purchase, "total_investment": total,
        "realistic_sale_price": realistic, "quick_sale_price": quick,
        "expected_profit": expected, "quick_sale_profit": quick_profit,
        "roi_percent": roi, "break_even_purchase_price": break_even,
        "target_purchase_price": target, "excellent_purchase_price": excellent,
        "required_discount": max(0, purchase - target),
    }

    risk_raw = raw.get("risk", {})
    liquidity_raw = raw.get("liquidity", {})
    negotiation_raw = raw.get("negotiation", {})
    verdict_raw = raw.get("verdict", {})
    risk = {"risk_score": _integer(risk_raw.get("risk_score", 100), minimum=0, maximum=100),
            "risk_level": _text(risk_raw.get("risk_level"), 50),
            "main_risks": _text_list(risk_raw.get("main_risks"), 12),
            "worst_case_expense": _integer(risk_raw.get("worst_case_expense", 0), minimum=0),
            "comment": _text(risk_raw.get("comment"), 1_000)}
    liquidity = {"liquidity_score": _integer(liquidity_raw.get("liquidity_score", 0), minimum=0, maximum=100),
                 "liquidity_level": _text(liquidity_raw.get("liquidity_level"), 50),
                 "comment": _text(liquidity_raw.get("comment"), 1_000)}
    negotiation = {"start_offer": _integer(negotiation_raw.get("start_offer", 0), minimum=0),
                   "target_purchase_price": target, "maximum_purchase_price": break_even,
                   "negotiation_arguments": _text_list(negotiation_raw.get("negotiation_arguments"), 10)}
    allowed_verdicts = {"excellent", "good", "only_after_discount", "borderline", "bad", "avoid"}
    code = verdict_raw.get("code") if verdict_raw.get("code") in allowed_verdicts else "borderline"
    verdict = {"code": code, "score": _integer(verdict_raw.get("score", 0), minimum=0, maximum=100),
               "should_inspect": bool(verdict_raw.get("should_inspect", False)),
               "summary": _text(verdict_raw.get("summary"), 1_000),
               "main_profit_factor": _text(verdict_raw.get("main_profit_factor"), 500),
               "main_loss_risk": _text(verdict_raw.get("main_loss_risk"), 500)}
    vehicle = {"model": car["car_model"], "year": car["year"], "mileage": car["mileage"],
               "region": car["region"], "asking_price": purchase}
    return {"vehicle": vehicle, "market": market, "repairs": repairs, "economics": economics,
            "risk": risk, "liquidity": liquidity,
            "inspection_checklist": _text_list(raw.get("inspection_checklist"), 12),
            "negotiation": negotiation, "verdict": verdict}
