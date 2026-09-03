from decimal import Decimal
import httpx
import pytest

from config import Settings
from schemas import PartSearchQuery, PartCondition, VehicleSpec
from services.apipoint import APIpointClient, InvalidMarketResponse, NotConfiguredError
from services.deal_engine import DealEngine, DealSettings
from services.parts import UnconfiguredPartsProvider, normalize_offers
from utils.messages import split_html_messages

def base_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN","x"); monkeypatch.setenv("OWNER_TELEGRAM_IDS","1")
    monkeypatch.setenv("TEST_MODE","true")

@pytest.mark.parametrize(("name","value","message"),[
    ("MAX_PHOTOS_PER_ANALYSIS","21","не может превышать"),
    ("MAX_PHOTO_SIZE_BYTES","0","больше нуля"),
    ("FIXED_EXPENSES_RUB","-1","отрицательным"),
    ("QUICK_SALE_COEFFICIENT","2","не больше 1"),
    ("OWNER_TELEGRAM_IDS","bad","Telegram ID"),
])
def test_config_rejects_invalid_values(monkeypatch,name,value,message):
    base_env(monkeypatch); monkeypatch.setenv(name,value)
    with pytest.raises(RuntimeError,match=message): Settings.from_env()

def test_deal_settings_validation():
    with pytest.raises(ValueError): DealSettings(Decimal("0"),0,0,0,0)
    with pytest.raises(ValueError): DealSettings(Decimal("1"),-1,0,0,0)
    engine=DealEngine(DealSettings(Decimal("1"),0,0,0,0))
    with pytest.raises(ValueError): engine.calculate(asking_price_rub=0,market=None,
        repairs=__import__('schemas').RepairEstimate(confirmed_min_rub=0,confirmed_likely_rub=0,
        confirmed_max_rub=0,potential_min_rub=0,potential_max_rub=0,catalog_version="v"))

@pytest.mark.asyncio
async def test_unconfigured_services_and_helpers():
    car=VehicleSpec(make="A",model="B",year=2020,asking_price_rub=1,region="R")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: pytest.fail("network"))) as client:
        with pytest.raises(NotConfiguredError): await APIpointClient(client,api_url="https://x",token=None).estimate(car)
    quote=await UnconfiguredPartsProvider().search(PartSearchQuery(make="A",model="B",year=2020,part_name="x",region="R"))
    assert quote.missing_parts==["x"]
    assert normalize_offers([],condition=PartCondition.NEW).offers_count==0

def test_apipoint_invalid_helpers_and_html_split():
    with pytest.raises(InvalidMarketResponse): APIpointClient._positive_money(True)
    with pytest.raises(InvalidMarketResponse): APIpointClient._positive_money(0)
    assert APIpointClient._decimal("bad") is None
    assert APIpointClient._optional_int(-1) is None
    assert len(split_html_messages("one\ntwo\nthree",limit=7)) > 1
