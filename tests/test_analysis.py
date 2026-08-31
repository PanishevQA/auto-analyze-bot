from handlers.analysis import sanitize_items, sanitize_prices, sanitize_risk
from utils.formatters import format_report


def test_sanitizers_and_report():
    items = sanitize_items([{"category": "critical", "item": "Цепь", "budget_economy": "10",
                             "budget_optimal": 20, "search_query": "цепь"}, {"category": "bad"}])
    assert len(items) == 1
    risk = sanitize_risk({"risk_score": 120, "risk_explanation": "ok", "inspection_checklist": ["x"]})
    assert risk["risk_score"] == 100
    car = {"car_model": "Toyota Camry", "year": 2014, "mileage": 100000,
           "price": 1000000, "region": "Москва и МО"}
    market = {"region_avg": 1, "rf_avg": 2, "quick": 3, "min": 1, "max": 4}
    scores = {"economy_total": 10, "optimal_total": 20, "total_costs": 1000030,
              "profit": -1000027, "profitability": 0}
    report = format_report(car, market, items, risk, scores)
    assert "Москва и МО" in report and "Средняя цена по всей РФ" in report
    assert "auto.ru/parts/search" in report


def test_sanitize_raw_market_prices():
    assert sanitize_prices(["100000", -1, None, 200000]) == [100000, 200000]
    assert sanitize_prices("100000") == []
