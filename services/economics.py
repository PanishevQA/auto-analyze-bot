from __future__ import annotations

from dataclasses import asdict, replace
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Any

from schemas import PartCondition, PartPriceEstimate, PartsStatus, RepairEstimate
from services.deal_engine import DealEngine, DealSettings
from services.parts import is_parts_quote_fresh


def settings_snapshot(engine: DealEngine, *, target_profit_rub: int | None = None) -> dict[str, Any]:
    settings = engine.settings if target_profit_rub is None else replace(
        engine.settings, target_profit_rub=target_profit_rub)
    result = asdict(settings)
    result["quick_sale_coefficient"] = str(result["quick_sale_coefficient"])
    return result


def engine_from_snapshot(snapshot: dict[str, Any] | None, fallback: DealEngine) -> tuple[DealEngine, bool]:
    if not snapshot:
        return fallback, False
    try:
        values=dict(snapshot)
        values["quick_sale_coefficient"]=Decimal(str(values["quick_sale_coefficient"]))
        return DealEngine(DealSettings(**values)), True
    except (TypeError, ValueError):
        return fallback, False


def required_parts(repairs: RepairEstimate) -> dict[str, Any]:
    return {item.defect_id: item for item in repairs.items if item.requires_part and item.defect_id}


def validate_parts_for_economics(
    repairs: RepairEstimate,
    quotes: list[PartPriceEstimate],
    *,
    condition: PartCondition,
    now: datetime,
    ttl: timedelta,
) -> tuple[list[PartPriceEstimate], bool, int, list[str]]:
    """Validate every required repair part by stable defect id and quote metadata."""
    required = required_parts(repairs)
    by_id = {quote.defect_id: quote for quote in quotes if quote.defect_id}
    checked: list[PartPriceEstimate] = []
    missing: list[str] = []
    total = 0
    for defect_id, item in required.items():
        quote = by_id.get(defect_id)
        if quote is None:
            missing.append(item.part_name or item.description)
            continue
        data = quote.query_data or {}
        compatible = (
            data.get("defect_id", defect_id) == defect_id
            and int(data.get("quantity", item.quantity)) == item.quantity
            and data.get("condition", condition.value) == condition.value
            and (not item.part_name or data.get("part_name", item.part_name).casefold() == item.part_name.casefold())
        )
        if quote.status is PartsStatus.READY and not is_parts_quote_fresh(quote, now, ttl):
            quote = quote.model_copy(update={"status": PartsStatus.STALE})
        if not compatible and quote.status is PartsStatus.READY:
            quote = quote.model_copy(update={"status": PartsStatus.NO_MATCH})
        checked.append(quote)
        if quote.status is PartsStatus.READY and quote.selected_price_rub is not None:
            total += quote.selected_price_rub
        elif quote.status is not PartsStatus.NOT_REQUIRED:
            missing.append(item.part_name or item.description)
    # Preserve unrelated/legacy entries for audit, but they never establish completeness.
    checked.extend(quote for quote in quotes if quote.defect_id not in required)
    return checked, not missing and len(required) == len(by_id.keys() & required.keys()), total, missing
