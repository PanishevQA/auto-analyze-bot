import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Any, Mapping

import httpx

from schemas import MarketEstimate, MarketSource, VehicleSpec

ADAPTER_VERSION = "apipoint-adapter-v1"


class APIpointError(RuntimeError):
    pass


class NotConfiguredError(APIpointError):
    pass


class InvalidMarketResponse(APIpointError):
    pass


class MarketUnavailableError(APIpointError):
    pass


@dataclass(frozen=True, slots=True)
class EndpointAdapter:
    alias: str
    source: MarketSource
    url: str
    price_path: str
    parameter_map: Mapping[str, str]

    def build_params(self, canonical: Mapping[str, Any]) -> dict[str, Any]:
        if not self.parameter_map:
            raise NotConfiguredError(f"Не задана карта параметров endpoint {self.alias}")
        return {
            external: canonical[internal]
            for internal, external in self.parameter_map.items()
            if canonical.get(internal) is not None
        }

    def normalize(self, payload: dict[str, Any]) -> int:
        value: Any = payload
        for part in self.price_path.split("."):
            if not isinstance(value, dict) or part not in value:
                raise InvalidMarketResponse(f"В {self.alias} отсутствует price_path {self.price_path}")
            value = value[part]
        if isinstance(value, bool) or value is None:
            raise InvalidMarketResponse("Цена отсутствует")
        try:
            price = int(value)
        except (TypeError, ValueError) as error:
            raise InvalidMarketResponse("Цена не является целым числом") from error
        if price <= 0 or price > 1_000_000_000:
            raise InvalidMarketResponse("Цена нулевая, отрицательная или аномальная")
        return price


class APIpointClient:
    def __init__(
        self, client: httpx.AsyncClient, adapters: list[EndpointAdapter], *,
        auth_header: str | None = None, auth_value: str | None = None,
        cache_ttl_seconds: int = 3_600,
    ) -> None:
        self.client = client
        self.adapters = adapters
        self.auth_header = auth_header
        self.auth_value = auth_value
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, MarketEstimate]] = {}

    async def estimate(self, vehicle: VehicleSpec) -> MarketEstimate:
        if not self.adapters:
            raise NotConfiguredError("APIpoint endpoints не настроены; укажите подтвержденный контракт")
        cache_key = self._cache_key(vehicle)
        cached = self._cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        failures: list[str] = []
        canonical = self._canonical_params(vehicle)
        for index, adapter in enumerate(self.adapters):
            try:
                estimate = await self._call_adapter(adapter, canonical, is_fallback=index > 0)
                self._cache[cache_key] = (time.monotonic() + self.cache_ttl_seconds, estimate)
                return estimate
            except (httpx.TimeoutException, httpx.HTTPError, InvalidMarketResponse,
                    NotConfiguredError) as error:
                failures.append(f"{adapter.alias}: {type(error).__name__}")
        raise MarketUnavailableError("APIpoint недоступен: " + ", ".join(failures))

    async def _call_adapter(
        self, adapter: EndpointAdapter, canonical: Mapping[str, Any], *, is_fallback: bool,
    ) -> MarketEstimate:
        headers = {}
        if self.auth_header and self.auth_value:
            headers[self.auth_header] = self.auth_value
        params = adapter.build_params(canonical)
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = await self.client.get(adapter.url, params=params, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError("Временная ошибка APIpoint", request=response.request,
                                                response=response)
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as error:
                    raise InvalidMarketResponse("Ответ APIpoint содержит поврежденный JSON") from error
                if not isinstance(payload, dict):
                    raise InvalidMarketResponse("Ответ APIpoint не является JSON-объектом")
                price = adapter.normalize(payload)
                return MarketEstimate(
                    source=adapter.source, endpoint_alias=adapter.alias,
                    market_price_rub=price, received_at=datetime.now(timezone.utc),
                    raw_payload=payload, adapter_version=ADAPTER_VERSION,
                    is_fallback=is_fallback,
                )
            except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
                last_error = error
                if (isinstance(error, httpx.HTTPStatusError)
                        and error.response.status_code != 429
                        and error.response.status_code < 500):
                    raise
                if attempt == 0:
                    await asyncio.sleep(0)
                    continue
                raise
        raise MarketUnavailableError("Неожиданное завершение retry") from last_error

    @staticmethod
    def _canonical_params(vehicle: VehicleSpec) -> dict[str, Any]:
        return {
            "make": vehicle.make.casefold().strip(),
            "model": vehicle.model.casefold().strip(),
            "year": vehicle.year,
            "generation": vehicle.generation.casefold().strip() if vehicle.generation else None,
            "mileage_km": vehicle.mileage_km,
            "region": vehicle.region.casefold().strip(),
            "engine_volume_l": str(vehicle.engine_volume_l) if vehicle.engine_volume_l else None,
            "fuel_type": vehicle.fuel_type.casefold().strip() if vehicle.fuel_type else None,
            "horsepower": vehicle.horsepower,
            "transmission": vehicle.transmission.casefold().strip() if vehicle.transmission else None,
            "drive": vehicle.drive.casefold().strip() if vehicle.drive else None,
            "body_type": vehicle.body_type.casefold().strip() if vehicle.body_type else None,
        }

    @classmethod
    def _cache_key(cls, vehicle: VehicleSpec) -> str:
        payload = json.dumps(cls._canonical_params(vehicle), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()
