from decimal import Decimal

import httpx
import pytest

from schemas import MarketSource, VehicleSpec
from services.apipoint import (APIpointClient, EndpointAdapter, InvalidMarketResponse,
                               MarketUnavailableError, NotConfiguredError)


def vehicle() -> VehicleSpec:
    return VehicleSpec(make="Toyota", model="Camry", year=2018, mileage_km=100_000,
                       asking_price_rub=2_000_000, region="Москва",
                       engine_volume_l=Decimal("2.5"), transmission="AT")


def adapter(alias: str, source: MarketSource, url: str, path: str = "data.price") -> EndpointAdapter:
    return EndpointAdapter(alias, source, url, path,
                           {"make": "brand", "model": "model", "year": "year"})


@pytest.mark.asyncio
async def test_avgcarprice_success_and_cache():
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["brand"] == "toyota"
        return httpx.Response(200, json={"data": {"price": 2_500_000}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = APIpointClient(client, [adapter("Avgcarprice", MarketSource.APIPOINT_AVGCARPRICE,
                                                  "https://api.test/avg")])
        first = await service.estimate(vehicle())
        second = await service.estimate(vehicle())
    assert first.source is MarketSource.APIPOINT_AVGCARPRICE
    assert second.market_price_rub == 2_500_000
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "500"])
async def test_avg_failure_falls_back_to_carprices(failure: str):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/avg":
            if failure == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            return httpx.Response(500, request=request)
        return httpx.Response(200, json={"result": {"amount": 2_400_000}})
    adapters = [
        adapter("Avgcarprice", MarketSource.APIPOINT_AVGCARPRICE, "https://api.test/avg"),
        adapter("Carprices", MarketSource.APIPOINT_CARPRICES, "https://api.test/fallback", "result.amount"),
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await APIpointClient(client, adapters).estimate(vehicle())
    assert result.source is MarketSource.APIPOINT_CARPRICES
    assert result.is_fallback is True


@pytest.mark.parametrize("value", [None, 0, -1, 1_000_000_001])
def test_invalid_prices_are_rejected(value):
    endpoint = adapter("Avgcarprice", MarketSource.APIPOINT_AVGCARPRICE, "https://api.test")
    with pytest.raises(InvalidMarketResponse):
        endpoint.normalize({"data": {"price": value}})


@pytest.mark.asyncio
async def test_not_configured_and_both_unavailable():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        with pytest.raises(NotConfiguredError):
            await APIpointClient(client, []).estimate(vehicle())
        with pytest.raises(MarketUnavailableError):
            await APIpointClient(client, [adapter("avg", MarketSource.APIPOINT_AVGCARPRICE,
                                                   "https://api.test")]).estimate(vehicle())
