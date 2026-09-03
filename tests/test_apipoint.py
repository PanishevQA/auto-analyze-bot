from decimal import Decimal
import json
import httpx
import pytest
from schemas import MarketConfidence, MarketSource, VehicleSpec
from services.apipoint import APIpointClient, APIpointPermanentError

def vehicle(): return VehicleSpec(make="Lada", model="Granta", year=2012, generation="I",
    horsepower=87, transmission="MANUAL", asking_price_rub=300000, region="Новосибирская область")

def avg_payload(error=False):
    return {"status": 200, "price": "1.5", "balance": "20.2", "result": {"avgcarprice": {
        "error": error, "error_msg": "bad" if error else None, "result": {"average": 500000,
        "minimalAverage": 450000, "offers_count": 8,
        "offers": [{"price": 490000, "distance": 12, "url": "https://auto.drom.ru/1"}]}}}}

@pytest.mark.asyncio
async def test_official_post_contract_nested_price_and_cache():
    calls=[]
    def handler(request):
        calls.append(request); body=json.loads(request.content)
        assert request.method == "POST" and str(request.url)=="https://apipoint.ru/api/call"
        assert request.headers["Authorization"] == "Bearer token"
        assert body["sources"] == "avgcarprice" and None not in body.values()
        return httpx.Response(200,json=avg_payload())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service=APIpointClient(client,api_url="https://apipoint.ru/api/call",token="token")
        result=await service.estimate(vehicle()); await service.estimate(vehicle())
    assert len(calls)==1 and result.market_price_rub==500000
    assert result.market_price_rub not in {1,20}
    assert result.minimal_average_rub==450000 and result.offers_count==8
    assert result.offers[0].distance==12 and result.request_cost_rub==Decimal("1.5")
    assert result.confidence is MarketConfidence.HIGH

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["error","missing","500","429"])
async def test_avg_failures_sequentially_fallback(mode):
    aliases=[]
    def handler(request):
        body=json.loads(request.content); aliases.append(body["sources"])
        if body["sources"]=="carprices":
            return httpx.Response(200,json={"status":200,"result":{"carprices":{"error":False,"result":{"avg_price":470000}}}})
        if mode=="error": return httpx.Response(200,json=avg_payload(True))
        if mode=="missing": return httpx.Response(200,json={"status":200,"result":{"avgcarprice":{"error":False,"result":{}}}})
        if mode=="broken": return httpx.Response(200,content=b"{")
        return httpx.Response(int(mode))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await APIpointClient(client,api_url="https://apipoint.ru/api/call",token="t").estimate(vehicle())
    assert aliases[-1]=="carprices" and result.source is MarketSource.APIPOINT_CARPRICES
    assert result.is_fallback and result.confidence is MarketConfidence.LIMITED
    assert aliases.count("avgcarprice") == (2 if mode in {"500","429"} else 1)

@pytest.mark.asyncio
async def test_normal_4xx_no_retry_and_no_fallback():
    calls=[]
    def handler(request): calls.append(json.loads(request.content)["sources"]); return httpx.Response(401)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(APIpointPermanentError):
            await APIpointClient(client,api_url="https://apipoint.ru/api/call",token="bad").estimate(vehicle())
    assert calls == ["avgcarprice"]

def test_body_supports_documented_automatic_and_filters_bad_offers():
    service=object.__new__(APIpointClient)
    car=vehicle().model_copy(update={"transmission":"AUTOMATIC","region":"Москва и МО"})
    body=service._body(car,"avgcarprice")
    assert body["transmission"]=="AUTOMATIC" and body["region"]=="Москва"
    assert service._offers([{"price":0},{"price":100,"distance":-1},"bad"])[0].price_rub==100
