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
        market_lines = [
            f"Источник: {market.source.value}\nEndpoint: {html.escape(market.endpoint_alias)}\n"
            f"Получено: {market.received_at:%d.%m.%Y %H:%M UTC}\n"
            f"Рынок: {money(market.market_price_rub)} ₽\n"
        ]
        if market.minimal_average_rub:
            market_lines.append(f"Минимальная средняя: {money(market.minimal_average_rub)} ₽\n")
        market_lines.append(
            f"Предложений: {market.offers_count if market.offers_count is not None else 'нет данных'}\n"
            f"Уверенность: {market.confidence.value}\n"
            f"Быстрая продажа: {money(deal.quick_sale_price_rub)} ₽\n"
            f"Fallback: {'да' if market.is_fallback else 'нет'}\n"
            f"Стоимость API-запроса: {market.request_cost_rub if market.request_cost_rub is not None else 'нет данных'} ₽"
        )
        market_block = "".join(market_lines)
    else:
        market_block = "Рыночная оценка не получена. Доступен только NO_RESULT; можно добавить MANUAL-оценку."
    limitations = "\n".join(f"• {html.escape(item)}" for item in condition.limitations) or "• Нет данных"
    score=lambda value: f"{value}/100" if value is not None else "не оценено"
    confirmed="\n".join(f"• {html.escape(d.part)}: {html.escape(d.code)}; фото {','.join(map(str,d.photo_numbers))}; confidence {d.confidence}" for d in condition.defects if d.status.value=="CONFIRMED") or "• Нет"
    possible="\n".join(f"• {html.escape(d.part)}: {html.escape(d.code)}; фото {','.join(map(str,d.photo_numbers))}; confidence {d.confidence}" for d in condition.defects if d.status.value=="POSSIBLE") or "• Нет"
    repair_warnings = "\n".join(f"• {html.escape(item)}" for item in repairs.warnings) or "• Нет"
    reasons = "\n".join(f"• {html.escape(item)}" for item in deal.reasons)
    checklist_items = list(condition.inspection_checklist) + list(condition.limitations)
    checklist_items += [f"Очно проверить {item.description}" for item in repairs.items
                        if item.status.value == "POSSIBLE" or item.requires_manual_check]
    checklist_items += ["Провести техническую диагностику", "Проверить документы и юридическую историю"]
    checklist = "\n".join(f"• {html.escape(item)}" for item in dict.fromkeys(checklist_items))
    confirmed_items = [item for item in repairs.items if item.status.value == "CONFIRMED"]
    bargaining = [f"Подтвержденный дефект: {item.description} ({money(item.likely_rub)} ₽)"
                  for item in confirmed_items]
    if deal.required_discount_rub:
        bargaining.append(f"Для целевой экономики требуется скидка {money(deal.required_discount_rub)} ₽")
    arguments = "\n".join(f"• {html.escape(item)}" for item in bargaining) or "• Подтвержденных аргументов пока нет"
    return f"""💹 <b>РЫНОК</b>
{market_block}

📷 <b>СОСТОЯНИЕ ПО ФОТО</b>
Покрытие: {condition.coverage.value}
Кузов: {score(condition.body_score)} · Салон: {score(condition.interior_score)} · Шины: {score(condition.tires_score)}
Подтверждено:
{confirmed}
Возможно:
{possible}
Ограничения:
{limitations}

🔧 <b>ВЛОЖЕНИЯ</b>
Подтверждено: {money(repairs.confirmed_min_rub)} / {money(repairs.confirmed_likely_rub)} / {money(repairs.confirmed_max_rub)} ₽
Потенциально: {money(repairs.potential_min_rub)} — {money(repairs.potential_max_rub)} ₽
Потенциальные дефекты не включены в основной repair likely.
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
Целевая прибыль: {money(deal.target_profit_rub)} ₽

🏁 <b>РЕШЕНИЕ: {deal.verdict.value}</b>
{reasons}

🔍 <b>ОСМОТР</b>
{checklist}

🤝 <b>АРГУМЕНТЫ ДЛЯ ТОРГА</b>
{arguments}

⚠️ <b>ОГРАНИЧЕНИЯ</b>
Оценка предварительная. Фотографии не заменяют очный осмотр. Требуются техническая диагностика,
проверка документов и юридической истории автомобиля."""
