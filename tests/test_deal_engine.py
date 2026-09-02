from datetime import datetime, timezone
from decimal import Decimal

from schemas import (Coverage, DealVerdict, DefectStatus, MarketEstimate, MarketSource,
                     RepairEstimate, RepairItem)
from services.deal_engine import DealEngine, DealSettings


def engine() -> DealEngine:
    return DealEngine(DealSettings(Decimal("0.92"), 5_000, 10_000, 40_000, 10_000))


def market(price: int = 1_000_000) -> MarketEstimate:
    return MarketEstimate(source=MarketSource.APIPOINT_AVGCARPRICE, endpoint_alias="avg",
                          market_price_rub=price, received_at=datetime.now(timezone.utc),
                          adapter_version="v1")


def repairs(*, likely: int = 20_000, potential: int = 0) -> RepairEstimate:
    return RepairEstimate(confirmed_min_rub=likely, confirmed_likely_rub=likely,
                          confirmed_max_rub=likely, potential_min_rub=potential,
                          potential_max_rub=potential, catalog_version="v1")


def test_exact_formulas_and_buy_boundary():
    result = engine().calculate(asking_price_rub=845_000, market=market(), repairs=repairs(),
                                coverage=Coverage.FULL)
    assert result.quick_sale_price_rub == 920_000
    assert result.total_investment_rub == 880_000
    assert result.expected_profit_rub == 40_000
    assert result.roi_percent == Decimal("4.55")
    assert result.break_even_buy_price_rub == 885_000
    assert result.max_buy_price_rub == 845_000
    assert result.excellent_buy_price_rub == 835_000
    assert result.required_discount_rub == 0
    assert result.verdict is DealVerdict.BUY


def test_watch_for_limited_coverage_or_possible_defect():
    limited = engine().calculate(asking_price_rub=800_000, market=market(), repairs=repairs(),
                                 coverage=Coverage.LIMITED)
    possible = engine().calculate(asking_price_rub=800_000, market=market(),
                                  repairs=repairs(potential=50_000), coverage=Coverage.FULL)
    assert limited.verdict is DealVerdict.WATCH
    assert possible.verdict is DealVerdict.WATCH


def test_pass_negative_roi_and_no_result():
    result = engine().calculate(asking_price_rub=950_000, market=market(), repairs=repairs(),
                                coverage=Coverage.FULL)
    assert result.verdict is DealVerdict.PASS
    assert result.roi_percent < 0
    missing = engine().calculate(asking_price_rub=950_000, market=None, repairs=repairs())
    assert missing.verdict is DealVerdict.NO_RESULT
    assert missing.quick_sale_price_rub == 0


def test_large_money_and_blocking_risk():
    result = engine().calculate(asking_price_rub=100_000_000, market=market(200_000_000),
                                repairs=repairs(likely=1_000_000), coverage=Coverage.FULL,
                                has_blocking_risk=True)
    assert result.total_investment_rub == 101_015_000
    assert result.verdict is DealVerdict.PASS

