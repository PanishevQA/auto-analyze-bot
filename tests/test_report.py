from datetime import datetime, timezone
from decimal import Decimal
from schemas import (ConditionAssessment, Coverage, DealResult, DealVerdict, MarketConfidence,
    MarketEstimate, MarketSource, PartCondition, PartOffer, PartPriceEstimate, PartsStatus,
    RepairEstimate, VehicleSpec)
from utils.deal_formatters import format_deal_details, format_deal_summary

def test_full_report_marks_fake_market_and_splits_parts():
    car=VehicleSpec(make="Ford",model="Focus",year=2015,asking_price_rub=500000,region="Москва")
    market=MarketEstimate(source=MarketSource.APIPOINT_AVGCARPRICE,endpoint_alias="avgcarprice",
        market_price_rub=700000,minimal_average_rub=650000,offers_count=3,confidence=MarketConfidence.LIMITED,
        received_at=datetime.now(timezone.utc),adapter_version="v",is_test_data=True,request_cost_rub=Decimal(0))
    repair=RepairEstimate(confirmed_min_rub=1000,confirmed_likely_rub=2000,confirmed_max_rub=3000,
        potential_min_rub=0,potential_max_rub=0,catalog_version="v",labor_likely_rub=2000)
    deal=DealResult(quick_sale_price_rub=640000,repair_likely_rub=12000,fixed_expenses_rub=5000,
        risk_reserve_rub=10000,total_investment_rub=527000,expected_profit_rub=113000,
        roi_percent=Decimal("21.44"),break_even_buy_price_rub=613000,max_buy_price_rub=573000,
        excellent_buy_price_rub=563000,required_discount_rub=0,target_profit_rub=40000,
        verdict=DealVerdict.WATCH,reasons=["проверка"],formula_version="v")
    offer=PartOffer(provider="official-test",part_name="Фара",condition=PartCondition.NEW,
        unit_price_rub=9000,delivery_price_rub=1000,in_stock=True,fetched_at=datetime.now(timezone.utc))
    parts=PartPriceEstimate(status=PartsStatus.READY,selected_price_rub=10000,min_price_rub=10000,
        median_price_rub=10000,max_price_rub=10000,offers_count=1,offers=[offer],provider="official-test",
        fetched_at=datetime.now(timezone.utc))
    assert "ТЕСТОВЫЙ РЕЖИМ" in format_deal_summary(car,deal,market)
    report=format_deal_details(car,market,ConditionAssessment(coverage=Coverage.UNAVAILABLE,
        limitations=["нет фото"]),repair,deal,[parts])
    assert "Работы:" in report and "Запчасти:" in report and "Фара" in report
