MISC_EXPENSES = 10_000


def calculate_market_metrics(region_prices: list[int], rf_prices: list[int], region: str) -> dict[str, int]:
    """Вычисляет рынок из сырых цен; YandexGPT не получает расчетных задач."""
    clean_region = [int(price) for price in region_prices if isinstance(price, int) and price > 0]
    clean_rf = [int(price) for price in rf_prices if isinstance(price, int) and price > 0]
    if not clean_rf:
        return {"region_avg": 0, "rf_avg": 0, "quick": 0, "min": 0, "max": 0}
    if region == "Весь РФ" or not clean_region:
        clean_region = clean_rf
    region_avg = sum(clean_region) // len(clean_region)
    return {
        "region_avg": region_avg,
        "rf_avg": sum(clean_rf) // len(clean_rf),
        "quick": region_avg * 95 // 100,
        "min": min(clean_region),
        "max": max(clean_region),
    }


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
