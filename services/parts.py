from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
from statistics import median
from typing import Protocol

from schemas import MatchStatus, PartCondition, PartOffer, PartPriceEstimate, PartSearchQuery, PartsStatus


class PartsPriceProvider(Protocol):
    async def search(self, query: PartSearchQuery) -> PartPriceEstimate: ...


def is_parts_quote_fresh(quote: PartPriceEstimate, now: datetime,
                         ttl: timedelta) -> bool:
    """Return whether a successful quote may be used as final economics input."""
    fetched = quote.fetched_at
    if quote.status is not PartsStatus.READY or fetched is None:
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return timedelta(0) <= now - fetched <= ttl


def mark_stale_quotes(quotes: list[PartPriceEstimate], *, now: datetime,
                      ttl: timedelta) -> list[PartPriceEstimate]:
    return [quote if quote.status is not PartsStatus.READY or is_parts_quote_fresh(quote, now, ttl)
            else quote.model_copy(update={"status": PartsStatus.STALE}) for quote in quotes]


def normalize_offers(offers: list[PartOffer], *, condition: PartCondition,
                     quantity: int = 1, provider: str | None = None,
                     min_offers: int = 1) -> PartPriceEstimate:
    deduplicated={str(offer.offer_url) if offer.offer_url else f"no-url-{index}":offer
                  for index,offer in enumerate(offers)}
    valid = [offer for offer in deduplicated.values() if offer.condition is condition and offer.in_stock
             and offer.unit_price_rub > 0 and offer.match_status in {MatchStatus.EXACT,MatchStatus.LIKELY}]
    totals = sorted((offer.unit_price_rub + offer.delivery_price_rub) * quantity for offer in valid)
    now = max((offer.fetched_at for offer in valid), default=datetime.now(timezone.utc))
    if not totals:
        return PartPriceEstimate(status=PartsStatus.NO_MATCH, provider=provider,
                                 fetched_at=now)
    if len(valid)<min_offers:
        return PartPriceEstimate(status=PartsStatus.INSUFFICIENT_DATA,offers_count=len(valid),offers=valid,
            provider=provider or (valid[0].provider if valid else None),fetched_at=now)
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
        material=query.model_dump_json()+"|"+self.provider.__class__.__name__
        key = hashlib.sha256(material.encode()).hexdigest()
        cached = self.cache.get(key); now = datetime.now(timezone.utc)
        if cached and cached.fetched_at and now - cached.fetched_at <= self.ttl: return cached
        fresh = await self.provider.search(query)
        if fresh.status is PartsStatus.READY: self.cache[key] = fresh
        elif cached: return cached.model_copy(update={"status": PartsStatus.STALE})
        return fresh

    async def close(self) -> None:
        close=getattr(self.provider,"close",None)
        if close: await close()
