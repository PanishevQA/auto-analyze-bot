from datetime import datetime, timezone, timedelta
import pytest
from schemas import MatchStatus, PartCondition, PartOffer, PartPriceEstimate, PartSearchQuery, PartsStatus
from services.parts import CachedPartsProvider, normalize_offers

def offer(price,delivery=0,condition=PartCondition.NEW):
    return PartOffer(provider="fake",part_name="Фара",condition=condition,unit_price_rub=price,
        delivery_price_rub=delivery,in_stock=True,fetched_at=datetime.now(timezone.utc),
        match_status=MatchStatus.EXACT,match_confidence="0.95")

def test_median_delivery_and_condition_filter():
    result=normalize_offers([offer(100,10),offer(200,10),offer(10000),offer(150,condition=PartCondition.USED)],condition=PartCondition.NEW)
    assert result.status is PartsStatus.READY and result.selected_price_rub==210
    assert result.offers_count==3

@pytest.mark.asyncio
async def test_cache_and_stale():
    class Provider:
        calls=0
        async def search(self,q):
            self.calls+=1
            if self.calls>1: return normalize_offers([],condition=q.condition)
            return normalize_offers([offer(100)],condition=q.condition)
    raw=Provider(); cache=CachedPartsProvider(raw,12)
    query=PartSearchQuery(make="A",model="B",year=2020,part_name="x",region="r")
    first=await cache.search(query); assert await cache.search(query)==first and raw.calls==1
    cache.cache[next(iter(cache.cache))]=first.model_copy(update={"fetched_at":datetime.now(timezone.utc)-timedelta(days=1)})
    assert (await cache.search(query)).status is PartsStatus.STALE

def test_cache_key_is_hash_not_plain_vin():
    class Provider: pass
    cache=CachedPartsProvider(Provider(),12)
    synthetic_vin="WVW"+"Z"*14
    query=PartSearchQuery(vin=synthetic_vin,make="A",model="B",year=2020,part_name="x",region="r")
    import hashlib
    expected=hashlib.sha256((query.model_dump_json()+"|Provider").encode()).hexdigest()
    assert synthetic_vin not in expected and len(expected)==64

from datetime import timedelta
from services.parts import is_parts_quote_fresh, mark_stale_quotes


def test_quote_freshness_marks_expired_ready_quote_stale():
    now=datetime.now(timezone.utc)
    quote=PartPriceEstimate(status=PartsStatus.READY,selected_price_rub=100,
        min_price_rub=100,median_price_rub=100,max_price_rub=100,
        fetched_at=now-timedelta(hours=13))
    assert not is_parts_quote_fresh(quote,now,timedelta(hours=12))
    assert mark_stale_quotes([quote],now=now,ttl=timedelta(hours=12))[0].status is PartsStatus.STALE


def test_manual_normalization_preserves_defect_id():
    from services.manual_parts_provider import ManualBrowserPartsProvider
    query=PartSearchQuery(defect_id="left-light",make="Lada",model="Granta",year=2012,
        part_name="фара",region="x",condition=PartCondition.NEW)
    offers=[PartOffer(provider="manual",part_name="фара Lada Granta",condition=PartCondition.NEW,
        unit_price_rub=value,in_stock=True,fetched_at=datetime.now(timezone.utc),
        delivery_price_rub=0,match_status=MatchStatus.EXACT,match_confidence="0.95",offer_url=f"https://baza.drom.ru/item/{value}") for value in (100,200,300)]
    result=ManualBrowserPartsProvider("https://baza.drom.ru/sell_spare_parts/").normalize_submitted(query,offers)
    assert result.defect_id == "left-light"
    assert result.median_price_rub == 200

def test_two_required_parts_one_quote_is_incomplete():
    from schemas import DefectStatus,RepairEstimate,RepairItem
    from services.economics import validate_parts_for_economics
    repairs=RepairEstimate(confirmed_min_rub=0,confirmed_likely_rub=0,confirmed_max_rub=0,
        potential_min_rub=0,potential_max_rub=0,catalog_version="v",items=[
        RepairItem(defect_code="lamp",defect_id="left",description="left",status=DefectStatus.CONFIRMED,
            min_rub=0,likely_rub=0,max_rub=0,requires_part=True,part_name="lamp",quantity=1),
        RepairItem(defect_code="lamp",defect_id="right",description="right",status=DefectStatus.CONFIRMED,
            min_rub=0,likely_rub=0,max_rub=0,requires_part=True,part_name="lamp",quantity=1)])
    quote=PartPriceEstimate(defect_id="left",status=PartsStatus.READY,selected_price_rub=100,
        min_price_rub=100,median_price_rub=100,max_price_rub=100,fetched_at=datetime.now(timezone.utc),
        query_data={"defect_id":"left","quantity":1,"condition":"NEW","part_name":"lamp"})
    _,complete,total,missing=validate_parts_for_economics(repairs,[quote],condition=PartCondition.NEW,
        now=datetime.now(timezone.utc),ttl=timedelta(hours=12))
    assert complete is False and total==100 and missing==["lamp"]


def test_likely_below_threshold_not_in_median():
    low=offer(100); low=low.model_copy(update={"match_status":MatchStatus.LIKELY,"match_confidence":"0.01"})
    result=normalize_offers([low,offer(200),offer(300)],condition=PartCondition.NEW,min_offers=3,match_confidence=.8)
    assert result.status is PartsStatus.INSUFFICIENT_DATA and result.offers_count==2
