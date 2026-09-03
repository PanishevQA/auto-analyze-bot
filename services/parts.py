from __future__ import annotations

from datetime import datetime, timezone, timedelta
from statistics import median
from typing import Protocol

from schemas import PartCondition, PartOffer, PartPriceEstimate, PartSearchQuery, PartsStatus


class PartsPriceProvider(Protocol):
    async def search(self, query: PartSearchQuery) -> PartPriceEstimate: ...


def normalize_offers(offers: list[PartOffer], *, condition: PartCondition,
                     quantity: int = 1, provider: str | None = None) -> PartPriceEstimate:
    valid = [offer for offer in offers if offer.condition is condition and offer.in_stock
             and offer.unit_price_rub > 0]
    totals = sorted((offer.unit_price_rub + offer.delivery_price_rub) * quantity for offer in valid)
    now = max((offer.fetched_at for offer in valid), default=datetime.now(timezone.utc))
    if not totals:
        return PartPriceEstimate(status=PartsStatus.NO_MATCH, provider=provider,
                                 fetched_at=now)
    # IQR fence avoids obvious outliers when enough observations exist.
    if len(totals) >= 4:
        lower = totals[:len(totals)//2]; upper = totals[(len(totals)+1)//2:]
        q1, q3 = median(lower), median(upper); iqr = q3 - q1
        filtered = [value for value in totals if q1 - 1.5 * iqr <= value <= q3 + 1.5 * iqr]
    else: filtered = totals
    selected = int(median(filtered))
    return PartPriceEstimate(status=PartsStatus.READY, selected_price_rub=selected,
        min_price_rub=min(filtered), median_price_rub=selected, max_price_rub=max(filtered),
        offers_count=len(valid), offers=valid, provider=provider or valid[0].provider, fetched_at=now)


class UnconfiguredPartsProvider:
    async def search(self, query: PartSearchQuery) -> PartPriceEstimate:
        return PartPriceEstimate(status=PartsStatus.UNAVAILABLE,
            missing_parts=[query.part_name], provider=None, fetched_at=datetime.now(timezone.utc))


class CachedPartsProvider:
    def __init__(self, provider: PartsPriceProvider, ttl_hours: int = 12) -> None:
        self.provider, self.ttl = provider, timedelta(hours=ttl_hours)
        self.cache: dict[str, PartPriceEstimate] = {}

    async def search(self, query: PartSearchQuery) -> PartPriceEstimate:
        key = query.model_dump_json(exclude={"vin"}) + (query.vin or "")
        cached = self.cache.get(key); now = datetime.now(timezone.utc)
        if cached and cached.fetched_at and now - cached.fetched_at <= self.ttl: return cached
        fresh = await self.provider.search(query)
        if fresh.status is PartsStatus.READY: self.cache[key] = fresh
        elif cached: return cached.model_copy(update={"status": PartsStatus.STALE})
        return fresh
