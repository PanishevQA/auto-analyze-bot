import html

from schemas import ConditionAssessment, DealResult, MarketEstimate, RepairEstimate, VehicleSpec, PartPriceEstimate, PartsStatus
from utils.formatters import money


def format_deal_summary(vehicle: VehicleSpec, deal: DealResult, market: MarketEstimate | None = None) -> str:
    risk = deal.reasons[0] if deal.reasons else "Требуется очная проверка"
    test_banner = "🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b>\nРыночная стоимость имитирована. Запрос к APIpoint не выполнялся.\n\n" if market and market.is_test_data else ""
    max_buy=money(deal.max_buy_price_rub) + " ₽" if deal.economics_complete else "не рассчитана"
    profit_label="Ожидаемая прибыль" if deal.economics_complete else "Предварительная прибыль без неизвестных деталей"
    incomplete="⚠️ <b>Экономика неполная</b>\n" if not deal.economics_complete else ""
    return test_banner + incomplete + (
        f"<b>{deal.verdict.value}</b> — {html.escape(vehicle.make)} {html.escape(vehicle.model)}\n"
        f"Цена продавца: {money(vehicle.asking_price_rub)} ₽\n"
        f"Максимальная цена покупки: {max_buy}\n"
        f"{profit_label}: {money(deal.expected_profit_rub)} ₽\n"
        f"Главный фактор: {html.escape(risk)}"
    )


def format_deal_details(
    vehicle: VehicleSpec, market: MarketEstimate | None,
    condition: ConditionAssessment, repairs: RepairEstimate, deal: DealResult,
    parts: list[PartPriceEstimate] | None = None,
) -> str:
    parts = parts or []
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
    ready_parts=[part for part in parts if part.status is PartsStatus.READY]
    missing=[name for part in parts if part.status is not PartsStatus.READY
             for name in (part.missing_parts or [str((part.query_data or {}).get("part_name","деталь"))])]
    parts_total=sum(part.selected_price_rub or 0 for part in ready_parts)
    parts_lines="\n".join(f"• {html.escape(part.offers[0].part_name if part.offers else 'Деталь')}: {money(part.selected_price_rub or 0)} ₽" for part in ready_parts) or "• Не требуются или цена не получена"
    quote_meta=""
    if ready_parts:
        quoted=ready_parts[0]
        quote_time=quoted.fetched_at.strftime("%d.%m.%Y %H:%M UTC") if quoted.fetched_at else "неизвестно"
        quote_meta=(f"\nИсточник: {html.escape(quoted.provider or 'не указан')}"
                    f"\nОбновлено: {quote_time}"
                    f"\nПредложений: {sum(item.offers_count for item in ready_parts)}")
    incomplete=("\n⚠️ Экономика рассчитана не полностью. Не оценено: " + ", ".join(map(html.escape,missing))) if missing else ""
    manual_queries="\n".join(f"• Поиск: {html.escape(str((part.query_data or {}).get('query','')))}\n  {html.escape(str((part.query_data or {}).get('manual_url','')))}"
        for part in parts if (part.query_data or {}).get("manual_url"))
    if manual_queries: incomplete += "\nОткройте Drom Базу вручную и пришлите 3–10 ссылок или скриншоты:\n"+manual_queries
    max_buy_detail=f"{money(deal.max_buy_price_rub)} ₽" if deal.economics_complete else "не рассчитана"
    excellent_detail=f"{money(deal.excellent_buy_price_rub)} ₽" if deal.economics_complete else "не рассчитана"
    profit_detail=f"{money(deal.expected_profit_rub)} ₽" if deal.economics_complete else "не рассчитана"
    roi_detail=f"{deal.roi_percent}%" if deal.economics_complete else "не рассчитан"
    break_even_detail=f"{money(deal.break_even_buy_price_rub)} ₽" if deal.economics_complete else "не рассчитана"
    discount_detail=f"{money(deal.required_discount_rub)} ₽" if deal.economics_complete else "не рассчитана"
    preliminary=(f"\nПредварительный результат без неизвестных запчастей: {money(deal.expected_profit_rub)} ₽"
                 if not deal.economics_complete and market else "")
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
Работы: {money(repairs.labor_likely_rub)} ₽
Запчасти: {money(parts_total)} ₽
Расходные материалы: {money(repairs.consumables_likely_rub)} ₽
Цены запчастей:
{parts_lines}{quote_meta}{incomplete}
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
Прибыль: {profit_detail}
ROI: {roi_detail}
Безубыточная цена: {break_even_detail}
Максимальная цена покупки: {max_buy_detail}
Отличная цена: {excellent_detail}
Требуемая скидка: {discount_detail}{preliminary}
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
