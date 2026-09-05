from pathlib import Path
import pytest
from schemas import PartCondition, PartSearchQuery, PartsStatus
from services.browser_parts_provider import FixtureBrowserPartsProvider, parse_visible_cards
from services.manual_parts_provider import validate_drom_baza_url

FIX=Path(__file__).parent/"fixtures"/"drom_baza"
def query(): return PartSearchQuery(make="Ford",model="Focus",year=2015,part_name="фара",side="LEFT",position="FRONT",region="Москва")

@pytest.mark.asyncio
async def test_fixture_provider_median_without_network():
    result=await FixtureBrowserPartsProvider((FIX/"search_results.html").read_text(),3).search(query())
    assert result.status is PartsStatus.READY and result.selected_price_rub==12000 and result.offers_count==3

def test_two_visible_prices_use_current_price():
    offer=parse_visible_cards((FIX/"two_prices.html").read_text())[0]
    assert offer.unit_price_rub==11000 and offer.old_price_rub==15000

@pytest.mark.asyncio
async def test_blocked_and_changed_layout_stop_safely():
    assert (await FixtureBrowserPartsProvider((FIX/"blocked.html").read_text()).search(query())).status is PartsStatus.BLOCKED
    assert (await FixtureBrowserPartsProvider((FIX/"changed_layout.html").read_text()).search(query())).status is PartsStatus.INSUFFICIENT_DATA

@pytest.mark.parametrize("url",["http://baza.drom.ru/1","https://evil.test/","https://baza.drom.ru.evil.test/1"])
def test_url_allowlist(url):
    with pytest.raises(ValueError): validate_drom_baza_url(url)

def test_money_parser_handles_kopecks_and_rejects_ranges():
    from utils.money_parser import parse_rubles
    assert parse_rubles("12 000,50 ₽") == 12001
    assert parse_rubles("12 000–15 000 ₽") is None
    assert parse_rubles("-100 ₽") is None


def test_card_preserves_actual_condition_stock_and_delivery():
    html='<article class="offer-card" data-condition="USED" data-in-stock="false"><h3><a href="https://baza.drom.ru/5">Фара</a></h3><span class="current-price">12 000 ₽</span></article>'
    offer=parse_visible_cards(html)[0]
    assert offer.condition is PartCondition.USED
    assert offer.in_stock is False
    assert offer.delivery_price_rub is None
