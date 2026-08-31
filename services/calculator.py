MISC_EXPENSES = 10_000


def calculate_total_costs(purchase_price: int, repair_budget_optimal: int) -> int:
    return purchase_price + repair_budget_optimal + MISC_EXPENSES


def calculate_profit(purchase_price: int, repair_budget_optimal: int, quick_sale_price: int) -> int:
    return quick_sale_price - calculate_total_costs(purchase_price, repair_budget_optimal)


def calculate_profitability_score(profit: int, total_costs: int) -> int:
    if total_costs <= 0:
        return 0
    return int(max(0, min(100, (profit / total_costs) * 100)))


def interpret_profitability_score(score: int) -> str:
    if score <= 30:
        return "❌ Убыточно или работа в ноль"
    if score <= 60:
        return "⚠️ Низкая маржа, высокий риск"
    if score <= 80:
        return "✅ Хороший вариант"
    return "🔥 Отличная сделка"


def interpret_risk_score(score: int) -> str:
    if score <= 30:
        return "🚨 Высокий риск (кот в мешке)"
    if score <= 60:
        return "⚠️ Средний риск"
    if score <= 80:
        return "✅ Относительно надежно"
    return "🛡️ Высокая надежность"


def final_recommendation(profitability: int, risk: int) -> str:
    if profitability > 60 and risk > 60:
        return "Автомобиль выглядит перспективно, но решение принимайте после очного осмотра."
    if profitability <= 30 or risk <= 30:
        return "Сделка требует повышенной осторожности и дополнительной диагностики."
    return "Условия пограничные: проверьте автомобиль и предусмотрите резерв бюджета."

