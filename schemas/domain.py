from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


SafeText = Annotated[str, Field(min_length=1, max_length=500)]


class SourceMode(StrEnum):
    DROM_API = "DROM_API"
    MANUAL = "MANUAL"


class MarketSource(StrEnum):
    APIPOINT_AVGCARPRICE = "APIPOINT_AVGCARPRICE"
    APIPOINT_CARPRICES = "APIPOINT_CARPRICES"
    MANUAL = "MANUAL"


class MarketConfidence(StrEnum):
    HIGH = "HIGH"
    LIMITED = "LIMITED"
    LOW = "LOW"


class DefectSeverity(StrEnum):
    MINOR = "MINOR"
    MEDIUM = "MEDIUM"
    SEVERE = "SEVERE"


class DefectStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    POSSIBLE = "POSSIBLE"


class Coverage(StrEnum):
    FULL = "FULL"
    LIMITED = "LIMITED"
    UNAVAILABLE = "UNAVAILABLE"


class AnalysisStatus(StrEnum):
    OK = "OK"
    LIMITED = "LIMITED"
    UNAVAILABLE = "UNAVAILABLE"


class DealVerdict(StrEnum):
    BUY = "BUY"
    WATCH = "WATCH"
    PASS = "PASS"
    NO_RESULT = "NO_RESULT"

class PartsStatus(StrEnum):
    READY="READY"; NOT_REQUIRED="NOT_REQUIRED"; NO_MATCH="NO_MATCH"
    UNAVAILABLE="UNAVAILABLE"; STALE="STALE"; ERROR="ERROR"
    BLOCKED="BLOCKED"; INSUFFICIENT_DATA="INSUFFICIENT_DATA"

class PartsSearchMode(StrEnum):
    DISABLED="DISABLED"; MANUAL_BROWSER="MANUAL_BROWSER"
    AUTHORIZED_DROM_BROWSER="AUTHORIZED_DROM_BROWSER"

class MatchStatus(StrEnum):
    EXACT="EXACT"; LIKELY="LIKELY"; REJECTED="REJECTED"


class VehicleSpec(StrictModel):
    source_url: HttpUrl | None = None
    source_mode: SourceMode = SourceMode.MANUAL
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1990, le=2100)
    generation: str | None = Field(default=None, max_length=100)
    mileage_km: int | None = Field(default=None, ge=0, le=2_000_000)
    asking_price_rub: int = Field(gt=0, le=1_000_000_000)
    region: str = Field(min_length=1, max_length=100)
    engine_volume_l: Decimal | None = Field(default=None, gt=0, le=20)
    fuel_type: str | None = Field(default=None, max_length=50)
    horsepower: int | None = Field(default=None, gt=0, le=5_000)
    transmission: str | None = Field(default=None, max_length=50)
    drive: str | None = Field(default=None, max_length=50)
    body_type: str | None = Field(default=None, max_length=50)
    seller_description: str | None = Field(default=None, max_length=10_000)
    vin: str | None = Field(default=None, pattern=r"^[A-HJ-NPR-Z0-9]{17}$")

    @field_validator("vin", mode="before")
    @classmethod
    def normalize_vin(cls, value):
        return value.strip().upper() if isinstance(value, str) and value.strip() else None


class MarketOffer(StrictModel):
    price_rub: int = Field(gt=0, le=1_000_000_000)
    distance: int | None = Field(default=None, ge=0)
    url: HttpUrl | None = None


class MarketEstimate(StrictModel):
    source: MarketSource
    endpoint_alias: str = Field(min_length=1, max_length=100)
    market_price_rub: int = Field(gt=0, le=1_000_000_000)
    received_at: datetime
    raw_payload: dict[str, Any] | None = None
    adapter_version: str = Field(min_length=1, max_length=50)
    is_fallback: bool = False
    minimal_average_rub: int | None = Field(default=None, gt=0, le=1_000_000_000)
    offers_count: int | None = Field(default=None, ge=0)
    offers: list[MarketOffer] = Field(default_factory=list, max_length=100)
    request_cost_rub: Decimal | None = Field(default=None, ge=0)
    balance_rub: Decimal | None = Field(default=None, ge=0)
    confidence: MarketConfidence = MarketConfidence.LIMITED
    is_test_data: bool = False

class PartCondition(StrEnum):
    NEW="NEW"; USED="USED"; UNKNOWN="UNKNOWN"

class PartSearchQuery(StrictModel):
    defect_id: str = Field(default_factory=lambda: uuid4().hex,min_length=1,max_length=64)
    vin: str | None = Field(default=None, pattern=r"^[A-HJ-NPR-Z0-9]{17}$")
    make: str; model: str; year: int; generation: str | None = None
    part_name: str; oem_number: str | None = None; side: str | None = None
    position: str | None = None
    search_phrase: str | None = Field(default=None,max_length=300)
    quantity: int = Field(default=1, gt=0); region: str
    condition: PartCondition = PartCondition.NEW

class PartOffer(StrictModel):
    provider: str; manufacturer: str | None = None; part_name: str
    oem_number: str | None = None; condition: PartCondition
    unit_price_rub: int = Field(gt=0); delivery_price_rub: int | None = Field(default=None, ge=0)
    quantity_available: int | None = Field(default=None, ge=0); delivery_days: int | None = Field(default=None, ge=0)
    in_stock: bool | None; offer_url: HttpUrl | None = None; fetched_at: datetime
    old_price_rub: int | None = Field(default=None, gt=0)
    location: str | None = None; delivery_text: str | None = None; seller: str | None = None
    source: str = "DROM_BAZA_BROWSER"
    match_status: MatchStatus = MatchStatus.REJECTED
    match_confidence: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    match_reasons: list[str] = Field(default_factory=list)

class PartPriceEstimate(StrictModel):
    defect_id: str | None = Field(default=None,max_length=64)
    status: PartsStatus; selected_price_rub: int | None = Field(default=None, ge=0)
    min_price_rub: int | None = Field(default=None, ge=0); median_price_rub: int | None = Field(default=None, ge=0)
    max_price_rub: int | None = Field(default=None, ge=0); offers_count: int = Field(default=0, ge=0)
    offers: list[PartOffer] = Field(default_factory=list); provider: str | None = None
    fetched_at: datetime | None = None; missing_parts: list[str] = Field(default_factory=list)
    query_data: dict[str, Any] | None = None


class PhotoReference(StrictModel):
    telegram_file_id: str = Field(min_length=1)
    order_number: int = Field(ge=1, le=20)
    mime_type: str
    size_bytes: int | None = Field(default=None, ge=0)
    local_temp_path: str | None = None
    telegram_file_unique_id: str | None = None
    media_group_id: str | None = None

    @field_validator("mime_type")
    @classmethod
    def supported_image(cls, value: str) -> str:
        if value not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Неподдерживаемый MIME-тип фотографии")
        return value


class VisibleDefect(StrictModel):
    defect_id: str = Field(default_factory=lambda: uuid4().hex,min_length=1,max_length=64)
    code: str = Field(pattern=r"^[a-z0-9_]+$")
    part: str = Field(min_length=1, max_length=200)
    severity: DefectSeverity
    status: DefectStatus
    photo_numbers: list[int] = Field(min_length=1, max_length=20)
    confidence: Decimal = Field(ge=0, le=1)
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("photo_numbers")
    @classmethod
    def valid_photo_numbers(cls, value: list[int]) -> list[int]:
        if any(number < 1 or number > 20 for number in value):
            raise ValueError("Номер фотографии должен быть от 1 до 20")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def low_confidence_is_possible(self) -> "VisibleDefect":
        if self.confidence < Decimal("0.6") and self.status is DefectStatus.CONFIRMED:
            raise ValueError("Дефект с низкой уверенностью должен иметь статус POSSIBLE")
        return self


class ConditionAssessment(StrictModel):
    coverage: Coverage
    body_score: int | None = Field(default=None, ge=0, le=100)
    interior_score: int | None = Field(default=None, ge=0, le=100)
    tires_score: int | None = Field(default=None, ge=0, le=100)
    defects: list[VisibleDefect] = Field(default_factory=list, max_length=100)
    limitations: list[SafeText] = Field(default_factory=list, max_length=30)
    inspection_checklist: list[SafeText] = Field(default_factory=list, max_length=30)
    model_uri: str = ""
    prompt_version: str = ""
    raw_payload: dict[str, Any] | None = None


class RepairItem(StrictModel):
    defect_code: str
    description: str
    status: DefectStatus
    min_rub: int = Field(ge=0)
    likely_rub: int = Field(ge=0)
    max_rub: int = Field(ge=0)
    requires_manual_check: bool = False
    operation: str = "REPAIR"
    requires_part: bool = False
    part_name: str | None = None
    side: str | None = None
    position: str | None = None
    defect_id: str | None = None
    quantity: int = Field(default=1, gt=0)


class RepairEstimate(StrictModel):
    confirmed_min_rub: int = Field(ge=0)
    confirmed_likely_rub: int = Field(ge=0)
    confirmed_max_rub: int = Field(ge=0)
    potential_min_rub: int = Field(ge=0)
    potential_max_rub: int = Field(ge=0)
    items: list[RepairItem] = Field(default_factory=list)
    warnings: list[SafeText] = Field(default_factory=list)
    catalog_version: str
    labor_likely_rub: int = Field(default=0, ge=0)
    consumables_likely_rub: int = Field(default=0, ge=0)


class DealResult(StrictModel):
    quick_sale_price_rub: int = Field(ge=0)
    repair_likely_rub: int = Field(ge=0)
    fixed_expenses_rub: int = Field(ge=0)
    risk_reserve_rub: int = Field(ge=0)
    total_investment_rub: int = Field(ge=0)
    expected_profit_rub: int
    roi_percent: Decimal
    break_even_buy_price_rub: int = Field(ge=0)
    max_buy_price_rub: int = Field(ge=0)
    excellent_buy_price_rub: int = Field(ge=0)
    required_discount_rub: int = Field(ge=0)
    target_profit_rub: int = Field(default=0, ge=0)
    verdict: DealVerdict
    reasons: list[SafeText]
    formula_version: str
    economics_complete: bool = True
