import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import logging
import time
from typing import Any, Protocol

import httpx

from schemas import (MarketConfidence, MarketEstimate, MarketOffer, MarketSource,
                     VehicleSpec)

logger = logging.getLogger(__name__)
ADAPTER_VERSION = "apipoint-official-v2"


class APIpointError(RuntimeError): pass
class NotConfiguredError(APIpointError): pass
class InvalidMarketResponse(APIpointError): pass
class MarketUnavailableError(APIpointError): pass
class APIpointPermanentError(APIpointError): pass
class NoMarketData(InvalidMarketResponse): pass
class TemporaryProviderError(InvalidMarketResponse): pass

class MarketPriceProvider(Protocol):
    async def estimate(self, vehicle: VehicleSpec, analysis_id: str | None = None) -> MarketEstimate: ...


class APIpointClient:
    def __init__(self, client: httpx.AsyncClient, *, api_url: str, token: str | None,
                 cache_ttl_seconds: int = 3600, high_confidence_offers: int = 8,
                 limited_confidence_offers: int = 3) -> None:
        self.client, self.api_url, self.token = client, api_url, token
        self.cache_ttl_seconds = cache_ttl_seconds
        self.high_confidence_offers = high_confidence_offers
        self.limited_confidence_offers = limited_confidence_offers
        self._cache: dict[str, tuple[float, MarketEstimate]] = {}

    async def estimate(self, vehicle: VehicleSpec, analysis_id: str | None = None) -> MarketEstimate:
        if not self.token:
            raise NotConfiguredError("APIPOINT_TOKEN не настроен")
        for cached_alias in ("avgcarprice", "carprices"):
            cached = self._cache.get(self._cache_key(vehicle, cached_alias))
            if cached and cached[0] > time.monotonic():
                return cached[1]
        for alias in ("avgcarprice", "carprices"):
            key = self._cache_key(vehicle, alias)
            try:
                payload = self._body(vehicle, alias)
                raw = await self._request(payload, alias, analysis_id)
                result = self._normalize(raw, alias, is_fallback=alias == "carprices")
                logger.info("APIpoint analysis_id=%s alias=%s status=OK request_cost_rub=%s fallback=%s",
                            analysis_id, alias, result.request_cost_rub, result.is_fallback)
                self._cache[key] = (time.monotonic() + self.cache_ttl_seconds, result)
                return result
            except APIpointPermanentError:
                raise
            except InvalidMarketResponse as error:
                if not isinstance(error, (NoMarketData, TemporaryProviderError)):
                    raise APIpointPermanentError(str(error)) from error
                logger.warning("APIpoint analysis_id=%s alias=%s status=NO_DATA error=%s",
                               analysis_id, alias, type(error).__name__)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as error:
                logger.warning("APIpoint analysis_id=%s alias=%s status=UNAVAILABLE error=%s",
                               analysis_id, alias, type(error).__name__)
        raise MarketUnavailableError("Avgcarprice и Carprices не вернули валидную цену")

    def _body(self, vehicle: VehicleSpec, alias: str) -> dict[str, Any]:
        body: dict[str, Any] = {"sources": alias, "marka": vehicle.make.upper(),
                                "model": vehicle.model.upper(), "year": vehicle.year}
        if alias == "avgcarprice":
            regions = {"Новосибирск и НО": "Новосибирская область", "Москва и МО": "Москва",
                       "Санкт-Петербург и ЛО": "Санкт-Петербург", "Екатеринбург": "Свердловская область",
                       "Красноярск": "Красноярский край", "Весь РФ": None}
            transmission = vehicle.transmission if vehicle.transmission in {
                "MANUAL", "AUTOMATIC", "ROBOT", "VARIATOR"
            } else None
            optional = {"generation": vehicle.generation, "horsepower": vehicle.horsepower,
                        "transmission": transmission, "region": regions.get(vehicle.region, vehicle.region)}
            body.update({key: value for key, value in optional.items() if value is not None})
        return body

    async def _request(self, body: dict[str, Any], alias: str,
                       analysis_id: str | None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                   "Accept": "application/json"}
        attempts=[]
        for attempt in range(2):
            started = time.monotonic()
            try:
                response = await self.client.post(self.api_url, json=body, headers=headers)
                duration = round(time.monotonic() - started, 3)
                logger.info("APIpoint analysis_id=%s alias=%s attempt=%s status=%s duration=%s",
                            analysis_id, alias, attempt + 1, response.status_code, duration)
                attempts.append({"attempt": attempt + 1, "http_status": response.status_code,
                                 "duration_seconds": duration})
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                if 400 <= response.status_code < 500:
                    raise APIpointPermanentError(f"APIpoint отклонил запрос: HTTP {response.status_code}")
                try:
                    value = response.json()
                except ValueError as error:
                    raise InvalidMarketResponse("Поврежденный JSON APIpoint") from error
                if not isinstance(value, dict):
                    raise InvalidMarketResponse("Ответ APIpoint не является объектом")
                value["_client_metadata"] = {"attempts": attempts, "paid_requests": len(attempts)}
                return value
            except httpx.HTTPStatusError as error:
                if error.response.status_code not in {429} and error.response.status_code < 500:
                    raise APIpointPermanentError(f"APIpoint отклонил запрос: HTTP {error.response.status_code}") from error
                if attempt == 0:
                    delay = 0.0
                    if error.response.status_code == 429:
                        try: delay = min(30.0, max(0.0, float(error.response.headers.get("Retry-After", "0"))))
                        except ValueError: delay = 0.0
                    await asyncio.sleep(delay)
                    continue
                raise
            except httpx.TimeoutException:
                if attempt == 0:
                    await asyncio.sleep(0)
                    continue
                raise
            except httpx.NetworkError:
                if attempt == 0:
                    await asyncio.sleep(0); continue
                raise
        raise MarketUnavailableError("retry исчерпан")

    def _normalize(self, payload: dict[str, Any], alias: str, *,
                   is_fallback: bool) -> MarketEstimate:
        status = payload.get("status")
        if not (isinstance(status, int) and not isinstance(status, bool) and 200 <= status <= 299):
            raise InvalidMarketResponse("Верхнеуровневый status неуспешен")
        try:
            block = payload["result"][alias]
            if block.get("error") is True:
                message=str(block.get("error_msg") or "APIpoint temporary provider error")
                if any(word in message.lower() for word in ("token", "авториз", "параметр", "parameter")):
                    raise APIpointPermanentError(message)
                raise TemporaryProviderError(message)
            result = block["result"]
            key="average" if alias == "avgcarprice" else "avg_price"
            if key not in result or result[key] is None: raise NoMarketData(f"{alias}: данных нет")
            price_raw = result[key]
        except (KeyError, TypeError) as error:
            raise InvalidMarketResponse(f"Неполный ответ {alias}") from error
        price = self._positive_money(price_raw)
        offers_count = self._optional_int(result.get("offers_count")) if alias == "avgcarprice" else None
        offers = self._offers(result.get("offers", [])) if alias == "avgcarprice" else []
        confidence = MarketConfidence.LIMITED if alias == "carprices" else self._confidence(offers_count)
        return MarketEstimate(
            source=MarketSource.APIPOINT_AVGCARPRICE if alias == "avgcarprice"
            else MarketSource.APIPOINT_CARPRICES,
            endpoint_alias=alias, market_price_rub=price,
            minimal_average_rub=self._optional_money(result.get("minimalAverage")),
            offers_count=offers_count, offers=offers,
            request_cost_rub=self._decimal(payload.get("price")),
            balance_rub=self._decimal(payload.get("balance")), confidence=confidence,
            received_at=datetime.now(timezone.utc), raw_payload=payload,
            adapter_version=ADAPTER_VERSION, is_fallback=is_fallback,
        )

    def _confidence(self, count: int | None) -> MarketConfidence:
        if count is None: return MarketConfidence.LIMITED
        if count >= self.high_confidence_offers: return MarketConfidence.HIGH
        if count >= self.limited_confidence_offers: return MarketConfidence.LIMITED
        return MarketConfidence.LOW

    @classmethod
    def _offers(cls, values: Any) -> list[MarketOffer]:
        if not isinstance(values, list): return []
        offers = []
        for value in values[:100]:
            if not isinstance(value, dict): continue
            try:
                offers.append(MarketOffer(price_rub=cls._positive_money(value.get("price")),
                                          distance=cls._optional_int(value.get("distance")),
                                          url=value.get("url") or None))
            except (ValueError, TypeError, InvalidMarketResponse): continue
        return offers

    @staticmethod
    def _positive_money(value: Any) -> int:
        if isinstance(value, bool): raise InvalidMarketResponse("Некорректная цена")
        try: price = int(value)
        except (TypeError, ValueError) as error: raise InvalidMarketResponse("Цена отсутствует") from error
        if price <= 0 or price > 1_000_000_000: raise InvalidMarketResponse("Цена вне диапазона")
        return price

    @classmethod
    def _optional_money(cls, value: Any) -> int | None:
        return None if value is None else cls._positive_money(value)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None: return None
        result = int(value); return result if result >= 0 else None

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None: return None
        try: result = Decimal(str(value))
        except InvalidOperation: return None
        return result if result >= 0 else None

    @staticmethod
    def _cache_key(vehicle: VehicleSpec, alias: str) -> str:
        data = {"marka": vehicle.make.upper(), "model": vehicle.model.upper(), "year": vehicle.year,
                "generation": vehicle.generation, "horsepower": vehicle.horsepower,
                "transmission": vehicle.transmission, "region": vehicle.region,
                "alias": alias, "adapter": ADAPTER_VERSION}
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class FakeAPIpointClient(APIpointClient):
    """Детерминированный APIpoint double: HTTP-клиент никогда не используется."""
    def __init__(self, *, scenario: str = "success", high_confidence_offers: int = 8,
                 limited_confidence_offers: int = 3) -> None:
        self.scenario = scenario
        self.high_confidence_offers = high_confidence_offers
        self.limited_confidence_offers = limited_confidence_offers
        self._cache = {}
        self.cache_ttl_seconds = 3600

    async def estimate(self, vehicle: VehicleSpec, analysis_id: str | None = None) -> MarketEstimate:
        if self.scenario == "all_sources_unavailable":
            raise MarketUnavailableError("TEST: источники недоступны")
        alias = "carprices" if self.scenario in {"avgcarprice_no_result", "fallback_to_carprices"} else "avgcarprice"
        if alias == "avgcarprice":
            raw = {"status": 200, "price": "0.00", "balance": "999999.00", "result": {alias: {
                "error": False, "error_msg": "", "result": {"average": 1_000_000,
                "minimalAverage": 900_000, "offers_count": 3, "offers": [
                    {"price": 950_000, "distance": 120_000, "url": "https://example.test/offer/1"},
                    {"price": 1_000_000, "distance": 110_000, "url": "https://example.test/offer/2"},
                    {"price": 1_050_000, "distance": 100_000, "url": "https://example.test/offer/3"}]}}}}
        else:
            raw = {"status": 200, "price": "0.00", "balance": "999999.00", "result": {alias: {
                "error": False, "error_msg": "", "result": {"avg_price": 980_000}}}}
        result = self._normalize(raw, alias, is_fallback=alias == "carprices")
        return result.model_copy(update={"is_test_data": True})

    def _confidence(self, count: int | None) -> MarketConfidence:
        if count is None: return MarketConfidence.LIMITED
        if count >= self.high_confidence_offers: return MarketConfidence.HIGH
        if count >= self.limited_confidence_offers: return MarketConfidence.LIMITED
        return MarketConfidence.LOW

    @classmethod
    def _offers(cls, values: Any) -> list[MarketOffer]:
        if not isinstance(values, list): return []
        offers = []
        for value in values[:100]:
            if not isinstance(value, dict): continue
            try:
                offers.append(MarketOffer(price_rub=cls._positive_money(value.get("price")),
                                          distance=cls._optional_int(value.get("distance")),
                                          url=value.get("url") or None))
            except (ValueError, TypeError, InvalidMarketResponse):
                continue
        return offers

    @staticmethod
    def _positive_money(value: Any) -> int:
        if isinstance(value, bool): raise InvalidMarketResponse("Некорректная цена")
        try: price = int(value)
        except (TypeError, ValueError) as error: raise InvalidMarketResponse("Цена отсутствует") from error
        if price <= 0 or price > 1_000_000_000: raise InvalidMarketResponse("Цена вне диапазона")
        return price

    @classmethod
    def _optional_money(cls, value: Any) -> int | None:
        return None if value is None else cls._positive_money(value)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None: return None
        result = int(value)
        return result if result >= 0 else None

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None: return None
        try: result = Decimal(str(value))
        except InvalidOperation: return None
        return result if result >= 0 else None

    @staticmethod
    def _cache_key(vehicle: VehicleSpec, alias: str) -> str:
        data = {"marka": vehicle.make.upper(), "model": vehicle.model.upper(), "year": vehicle.year,
                "generation": vehicle.generation, "horsepower": vehicle.horsepower,
                "transmission": vehicle.transmission, "region": vehicle.region,
                "alias": alias, "adapter": ADAPTER_VERSION}
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
