from datetime import datetime, timezone, timedelta
import pytest
from schemas import MatchStatus, PartCondition, PartOffer, PartSearchQuery, PartsStatus
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
