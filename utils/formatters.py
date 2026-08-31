import html
from typing import Any

from services.calculator import (final_recommendation, interpret_profitability_score,
                                 interpret_risk_score)
from services.link_generator import generate_search_links


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _items(items: list[dict[str, Any]], category: str) -> str:
    rows = []
    for item in items:
        if item.get("category") != category:
            continue
        title = html.escape(str(item.get("item", "Работа")))
        economy = money(int(item.get("budget_economy", 0)))
        optimal = money(int(item.get("budget_optimal", 0)))
        links = generate_search_links(str(item.get("search_query", title)))
        rows.append(f"• {title}: {economy} / {optimal} ₽ — <a href=\"{links['auto_ru']}\">Auto.ru</a>, <a href=\"{links['drom']}\">Drom</a>, <a href=\"{links['exist']}\">Exist</a>")
    return "\n".join(rows) or "• Не требуется / нет данных"


def format_summary(data: dict[str, Any]) -> str:
    return (f"<b>Проверьте данные</b>\n\n🚗 {html.escape(data['car_model'])}\n"
            f"📅 {data['year']} · 🛣 {money(data['mileage'])} км\n"
            f"⚙️ {html.escape(data['engine'])}\n💰 {money(data['price'])} ₽\n"
            f"📄 <b>Описание объявления:</b> {html.escape(data['listing_description'])}\n"
            f"📷 <b>Повреждения на фото:</b> {html.escape(data['photo_damage'])}\n"
            f"🛠 <b>Дополнительные данные:</b> {html.escape(data['user_issues'])}")


def format_report(car: dict[str, Any], market: dict[str, int], items: list[dict[str, Any]],
                  risk: dict[str, Any], scores: dict[str, int]) -> str:
    checklist = "\n".join(f"• {html.escape(str(x))}" for x in risk["inspection_checklist"])
    return f"""📊 <b>ОТЧЕТ ПО АВТОМОБИЛЮ</b>

🚗 <b>Авто:</b> {html.escape(car['car_model'])}
📅 <b>Год:</b> {car['year']}
🛣 <b>Пробег:</b> {money(car['mileage'])} км
💰 <b>Цена покупки:</b> {money(car['price'])} ₽

💹 <b>АНАЛИЗ РЫНКА</b>
• Средняя цена в регионе ({html.escape(car['region'])}): {money(market['region_avg'])} ₽
• Средняя цена по всей РФ: {money(market['rf_avg'])} ₽
• Цена быстрой продажи: {money(market['quick'])} ₽
• Диапазон: {money(market['min'])} — {money(market['max'])} ₽

🔧 <b>СМЕТА</b>
<b>Критический ремонт:</b>
{_items(items, 'critical')}
<b>Товарный вид:</b>
{_items(items, 'appearance')}
<b>Расходники и ТО:</b>
{_items(items, 'maintenance')}
<b>Итого:</b> эконом {money(scores['economy_total'])} ₽; оптимально {money(scores['optimal_total'])} ₽

💵 <b>ФИНАНСОВЫЙ ИТОГ</b>
• Затраты: {money(scores['total_costs'])} ₽
• Потенциальная прибыль: {money(scores['profit'])} ₽
• Рентабельность: {scores['profitability']}%
📊 {interpret_profitability_score(scores['profitability'])}

⚠️ <b>ОЦЕНКА РИСКОВ: {risk['risk_score']}/100</b>
{interpret_risk_score(risk['risk_score'])}
{html.escape(risk['risk_explanation'])}

🔍 <b>ЧЕК-ЛИСТ ПРИ ОСМОТРЕ</b>
{checklist or '• Нет данных'}

💡 <b>РЕКОМЕНДАЦИЯ</b>
{final_recommendation(scores['profitability'], risk['risk_score'])}"""


def _commercial_items(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        status = "подтверждено" if item["status"] == "confirmed" else "возможный риск"
        rows.append(
            f"• <b>{html.escape(item['name'])}</b> ({status}): {money(item['total_cost'])} ₽\n"
            f"  Детали {money(item['parts_cost'])} ₽ + работа {money(item['labor_cost'])} ₽. "
            f"{html.escape(item['reason'])}"
        )
    return "\n".join(rows) or "• Нет"


def format_commercial_report(data: dict[str, Any]) -> str:
    vehicle, market = data["vehicle"], data["market"]
    repairs, economics = data["repairs"], data["economics"]
    risk, liquidity = data["risk"], data["liquidity"]
    negotiation, verdict = data["negotiation"], data["verdict"]
    risks = "\n".join(f"• {html.escape(x)}" for x in risk["main_risks"]) or "• Нет данных"
    checklist = "\n".join(f"• {html.escape(x)}" for x in data["inspection_checklist"]) or "• Нет данных"
    arguments = "\n".join(f"• {html.escape(x)}" for x in negotiation["negotiation_arguments"]) or "• Нет данных"
    inspect = "Да" if verdict["should_inspect"] else "Нет"
    return f"""📊 <b>КОММЕРЧЕСКИЙ АНАЛИЗ АВТОМОБИЛЯ</b>

🚗 <b>{html.escape(vehicle['model'])}</b>, {vehicle['year']}
🛣 {money(vehicle['mileage'])} км · 📍 {html.escape(vehicle['region'])}
💰 Цена продавца: {money(vehicle['asking_price'])} ₽

💹 <b>РЫНОК</b>
• Регион: {money(market['region']['low'])} — <b>{money(market['region']['mid'])}</b> — {money(market['region']['high'])} ₽
• РФ: {money(market['rf']['low'])} — <b>{money(market['rf']['mid'])}</b> — {money(market['rf']['high'])} ₽
• Реалистичная продажа: <b>{money(market['realistic_sale_price'])} ₽</b>
• Быстрая продажа: <b>{money(market['quick_sale_price'])} ₽</b>
{html.escape(market['market_comment'])}

🔧 <b>КРИТИЧЕСКИЙ РЕМОНТ</b>
{_commercial_items(repairs['critical_repairs'])}

✨ <b>ПОДГОТОВКА К ПРОДАЖЕ</b>
{_commercial_items(repairs['sale_preparation'])}

🛠 <b>ОБСЛУЖИВАНИЕ</b>
{_commercial_items(repairs['maintenance'])}

⚠️ <b>ПОТЕНЦИАЛЬНЫЕ РЕМОНТЫ (НЕ ВКЛЮЧЕНЫ В БЮДЖЕТ)</b>
{_commercial_items(repairs['potential_repairs'])}

• Минимальная подготовка: {money(repairs['minimum_preparation_cost'])} ₽
• Рекомендуемая подготовка: {money(repairs['recommended_preparation_cost'])} ₽
• Резерв риска: {money(repairs['risk_reserve'])} ₽

💵 <b>ЭКОНОМИКА</b>
• Общие вложения: {money(economics['total_investment'])} ₽
• Ожидаемая прибыль: <b>{money(economics['expected_profit'])} ₽</b>
• Прибыль при быстрой продаже: {money(economics['quick_sale_profit'])} ₽
• ROI: <b>{economics['roi_percent']}%</b>
• Безубыточная цена входа: {money(economics['break_even_purchase_price'])} ₽
• Целевая цена покупки: <b>{money(economics['target_purchase_price'])} ₽</b>
• Отличная цена покупки: {money(economics['excellent_purchase_price'])} ₽
• Требуемая скидка: {money(economics['required_discount'])} ₽

🚨 <b>РИСК: {risk['risk_score']}/100 — {html.escape(risk['risk_level'])}</b>
{risks}
Худший дополнительный расход: {money(risk['worst_case_expense'])} ₽
{html.escape(risk['comment'])}

🏷 <b>ЛИКВИДНОСТЬ: {liquidity['liquidity_score']}/100 — {html.escape(liquidity['liquidity_level'])}</b>
{html.escape(liquidity['comment'])}

🔍 <b>ЧЕК-ЛИСТ ОСМОТРА</b>
{checklist}

🤝 <b>ТОРГ</b>
• Начать с: {money(negotiation['start_offer'])} ₽
• Цель: {money(negotiation['target_purchase_price'])} ₽
• Максимум: {money(negotiation['maximum_purchase_price'])} ₽
{arguments}

🏁 <b>ВЕРДИКТ: {verdict['code']} ({verdict['score']}/100)</b>
Стоит ехать смотреть: <b>{inspect}</b>
{html.escape(verdict['summary'])}
Фактор прибыли: {html.escape(verdict['main_profit_factor'])}
Главный риск убытка: {html.escape(verdict['main_loss_risk'])}"""
