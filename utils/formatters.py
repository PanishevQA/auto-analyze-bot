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


def format_summary(data: dict[str, Any], typical: list[str]) -> str:
    issues = "\n".join(f"• {html.escape(str(x))}" for x in typical) or "• Нет данных"
    return (f"<b>Проверьте данные</b>\n\n🚗 {html.escape(data['car_model'])}\n"
            f"📅 {data['year']} · 🛣 {money(data['mileage'])} км\n"
            f"⚙️ {html.escape(data['engine'])}\n💰 {money(data['price'])} ₽\n"
            f"📄 <b>Описание объявления:</b> {html.escape(data['listing_description'])}\n"
            f"📷 <b>Повреждения на фото:</b> {html.escape(data['photo_damage'])}\n"
            f"🛠 <b>Другие проблемы:</b> {html.escape(data['user_issues'])}\n\n"
            f"<b>Типичные проблемы:</b>\n{issues}")


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
