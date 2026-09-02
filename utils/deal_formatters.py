import html

from schemas import ConditionAssessment, DealResult, MarketEstimate, RepairEstimate, VehicleSpec
from utils.formatters import money


def format_deal_summary(vehicle: VehicleSpec, deal: DealResult) -> str:
    risk = deal.reasons[0] if deal.reasons else "Требуется очная проверка"
    return (
        f"<b>{deal.verdict.value}</b> — {html.escape(vehicle.make)} {html.escape(vehicle.model)}\n"
        f"Цена продавца: {money(vehicle.asking_price_rub)} ₽\n"
        f"Максимальная цена покупки: {money(deal.max_buy_price_rub)} ₽\n"
        f"Ожидаемая прибыль: {money(deal.expected_profit_rub)} ₽\n"
        f"Главный фактор: {html.escape(risk)}"
    )


def format_deal_details(
    vehicle: VehicleSpec, market: MarketEstimate | None,
    condition: ConditionAssessment, repairs: RepairEstimate, deal: DealResult,
) -> str:
    if market:
        market_block = (
            f"Источник: {market.source.value}\nEndpoint: {html.escape(market.endpoint_alias)}\n"
            f"Получено: {market.received_at:%d.%m.%Y %H:%M UTC}\n"
            f"Рынок: {money(market.market_price_rub)} ₽\n"
            f"Быстрая продажа: {money(deal.quick_sale_price_rub)} ₽\n"
            f"Fallback: {'да' if market.is_fallback else 'нет'}"
        )
    else:
        market_block = "Рыночная оценка не получена. Доступен только NO_RESULT; можно добавить MANUAL-оценку."
    limitations = "\n".join(f"• {html.escape(item)}" for item in condition.limitations) or "• Нет данных"
    repair_warnings = "\n".join(f"• {html.escape(item)}" for item in repairs.warnings) or "• Нет"
    reasons = "\n".join(f"• {html.escape(item)}" for item in deal.reasons)
    return f"""💹 <b>РЫНОК</b>
{market_block}

📷 <b>СОСТОЯНИЕ ПО ФОТО</b>
Покрытие: {condition.coverage.value}
На этапе P0 фотографии не анализируются.
Ограничения:
{limitations}

🔧 <b>ВЛОЖЕНИЯ</b>
Подтверждено: {money(repairs.confirmed_min_rub)} / {money(repairs.confirmed_likely_rub)} / {money(repairs.confirmed_max_rub)} ₽
Потенциально: {money(repairs.potential_min_rub)} — {money(repairs.potential_max_rub)} ₽
Фиксированные расходы: {money(deal.fixed_expenses_rub)} ₽
Резерв риска: {money(deal.risk_reserve_rub)} ₽
Предупреждения каталога:
{repair_warnings}

💵 <b>ЭКОНОМИКА</b>
Цена продавца: {money(vehicle.asking_price_rub)} ₽
Быстрая продажа: {money(deal.quick_sale_price_rub)} ₽
Ремонт: {money(deal.repair_likely_rub)} ₽
Общие вложения: {money(deal.total_investment_rub)} ₽
Прибыль: {money(deal.expected_profit_rub)} ₽
ROI: {deal.roi_percent}%
Безубыточная цена: {money(deal.break_even_buy_price_rub)} ₽
Максимальная цена покупки: {money(deal.max_buy_price_rub)} ₽
Отличная цена: {money(deal.excellent_buy_price_rub)} ₽
Требуемая скидка: {money(deal.required_discount_rub)} ₽

🏁 <b>РЕШЕНИЕ: {deal.verdict.value}</b>
{reasons}

⚠️ <b>ОГРАНИЧЕНИЯ</b>
Оценка предварительная. Фотографии не заменяют очный осмотр. Требуются техническая диагностика,
проверка документов и юридической истории автомобиля."""
