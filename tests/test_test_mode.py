import pytest
from config import Settings
from schemas import VehicleSpec
from services.apipoint import FakeAPIpointClient
from utils.deal_formatters import format_deal_summary
from services.deal_engine import DealEngine, DealSettings
from schemas import Coverage, RepairEstimate
from decimal import Decimal

def configure(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN","x"); monkeypatch.setenv("OWNER_TELEGRAM_IDS","1")

def test_test_mode_default_false_and_requires_token(monkeypatch):
    configure(monkeypatch); monkeypatch.delenv("TEST_MODE",raising=False); monkeypatch.delenv("APIPOINT_TOKEN",raising=False)
    with pytest.raises(RuntimeError,match="APIPOINT_TOKEN"): Settings.from_env()

def test_test_mode_strict(monkeypatch):
    configure(monkeypatch); monkeypatch.setenv("TEST_MODE","yes123")
    with pytest.raises(RuntimeError,match="true или false"): Settings.from_env()

@pytest.mark.asyncio
async def test_fake_is_deterministic_without_network_and_report_marked():
    car=VehicleSpec(make="Ford",model="Focus",year=2015,asking_price_rub=500000,region="Москва")
    provider=FakeAPIpointClient(); first=await provider.estimate(car); second=await provider.estimate(car)
    assert first.market_price_rub==second.market_price_rub and first.is_test_data
    repairs=RepairEstimate(confirmed_min_rub=0,confirmed_likely_rub=0,confirmed_max_rub=0,
        potential_min_rub=0,potential_max_rub=0,catalog_version="x")
    engine=DealEngine(DealSettings(Decimal("0.92"),5000,10000,40000,10000))
    deal=engine.calculate(asking_price_rub=500000,market=first,repairs=repairs,coverage=Coverage.FULL)
    assert "ТЕСТОВЫЙ РЕЖИМ" in format_deal_summary(car,deal,first)
