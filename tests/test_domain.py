from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas import (ConditionAssessment, Coverage, DefectSeverity, DefectStatus,
                     MarketEstimate, MarketSource, PhotoReference, SourceMode,
                     VehicleSpec, VisibleDefect)


def test_vehicle_and_market_models_reject_invalid_money():
    vehicle = VehicleSpec(source_mode=SourceMode.MANUAL, make="Lada", model="Vesta", year=2020,
                          asking_price_rub=1_000_000, region="Москва")
    assert vehicle.asking_price_rub == 1_000_000
    with pytest.raises(ValidationError):
        MarketEstimate(source=MarketSource.MANUAL, endpoint_alias="manual", market_price_rub=0,
                       received_at=datetime.now(timezone.utc), adapter_version="v1")


def test_visible_defect_requires_photo_and_valid_confidence():
    defect = VisibleDefect(code="scratch_minor", part="Дверь", severity=DefectSeverity.MINOR,
                           status=DefectStatus.CONFIRMED, photo_numbers=[1],
                           confidence=Decimal("0.9"))
    assessment = ConditionAssessment(coverage=Coverage.LIMITED, defects=[defect],
                                     model_uri="qwen", prompt_version="v1")
    assert assessment.defects[0].photo_numbers == [1]
    with pytest.raises(ValidationError):
        VisibleDefect(code="scratch_minor", part="Дверь", severity=DefectSeverity.MINOR,
                      status=DefectStatus.CONFIRMED, photo_numbers=[], confidence=Decimal("0.9"))
    with pytest.raises(ValidationError):
        VisibleDefect(code="scratch_minor", part="Дверь", severity=DefectSeverity.MINOR,
                      status=DefectStatus.CONFIRMED, photo_numbers=[1], confidence=Decimal("0.4"))


def test_vision_schema_forbids_financial_fields_and_photo_mime_is_limited():
    with pytest.raises(ValidationError):
        ConditionAssessment(coverage=Coverage.FULL, defects=[], model_uri="qwen",
                            prompt_version="v1", market_price=100)
    with pytest.raises(ValidationError):
        PhotoReference(telegram_file_id="id", order_number=1, mime_type="application/pdf")

