from services.calculator import *


def test_financial_math():
    assert calculate_total_costs(1_000_000, 100_000) == 1_110_000
    assert calculate_profit(1_000_000, 100_000, 1_300_000) == 190_000
    assert calculate_profitability_score(190_000, 1_110_000) == 17


def test_score_bounds_and_interpretations():
    assert calculate_profitability_score(-1, 10) == 0
    assert calculate_profitability_score(1000, 1) == 100
    assert calculate_profitability_score(1, 0) == 0
    assert "Убыточно" in interpret_profitability_score(30)
    assert "Высокая надежность" in interpret_risk_score(81)


def test_market_metrics_are_calculated_in_python():
    result = calculate_market_metrics([150_000, 180_000, 210_000], [160_000, 200_000], "Москва и МО")
    assert result == {"region_avg": 180_000, "rf_avg": 180_000, "quick": 171_000,
                      "min": 150_000, "max": 210_000}
    rf = calculate_market_metrics([], [100_000, 200_000], "Весь РФ")
    assert rf["region_avg"] == rf["rf_avg"] == 150_000
