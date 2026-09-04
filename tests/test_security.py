import asyncio
from types import SimpleNamespace

from utils.access import OwnerAccessMiddleware
from utils.deal_formatters import format_deal_summary
from utils.messages import split_html_messages
from schemas import DealResult, DealVerdict, SourceMode, VehicleSpec
from decimal import Decimal


def test_html_escaping_and_safe_split():
    vehicle = VehicleSpec(source_mode=SourceMode.MANUAL, make="<b>Lada</b>", model="Vesta",
                          year=2020, asking_price_rub=1, region="Москва")
    deal = DealResult(quick_sale_price_rub=1, repair_likely_rub=0, fixed_expenses_rub=0,
                      risk_reserve_rub=0, total_investment_rub=1, expected_profit_rub=0,
                      roi_percent=Decimal("0"), break_even_buy_price_rub=1,
                      max_buy_price_rub=1, excellent_buy_price_rub=1,
                      required_discount_rub=0, verdict=DealVerdict.BUY,
                      reasons=["ok"], formula_version="v1")
    rendered = format_deal_summary(vehicle, deal)
    assert "&lt;b&gt;Lada&lt;/b&gt;" in rendered
    chunks = split_html_messages(("<b>строка</b>\n" * 500), limit=200)
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert all(chunk.count("<b>") == chunk.count("</b>") for chunk in chunks)


def test_owner_middleware_rejects_before_handler():
    called = False
    async def handler(event, data):
        nonlocal called
        called = True
    middleware = OwnerAccessMiddleware(frozenset({1}))
    asyncio.run(middleware(handler, SimpleNamespace(), {"event_from_user": SimpleNamespace(id=2)}))
    assert called is False
