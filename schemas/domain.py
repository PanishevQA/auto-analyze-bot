from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

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


class MarketEstimate(StrictModel):
    source: MarketSource
    endpoint_alias: str = Field(min_length=1, max_length=100)
    market_price_rub: int = Field(gt=0, le=1_000_000_000)
    received_at: datetime
    raw_payload: dict[str, Any] | None = None
    adapter_version: str = Field(min_length=1, max_length=50)
    is_fallback: bool = False


class PhotoReference(StrictModel):
    telegram_file_id: str = Field(min_length=1)
    order_number: int = Field(ge=1, le=20)
    mime_type: str
    size_bytes: int | None = Field(default=None, ge=0)
    local_temp_path: str | None = None

    @field_validator("mime_type")
    @classmethod
    def supported_image(cls, value: str) -> str:
        if value not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Неподдерживаемый MIME-тип фотографии")
        return value


class VisibleDefect(StrictModel):
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
    model_uri: str
    prompt_version: str
    raw_payload: dict[str, Any] | None = None


class RepairItem(StrictModel):
    defect_code: str
    description: str
    status: DefectStatus
    min_rub: int = Field(ge=0)
    likely_rub: int = Field(ge=0)
    max_rub: int = Field(ge=0)
    requires_manual_check: bool = False


class RepairEstimate(StrictModel):
    confirmed_min_rub: int = Field(ge=0)
    confirmed_likely_rub: int = Field(ge=0)
    confirmed_max_rub: int = Field(ge=0)
    potential_min_rub: int = Field(ge=0)
    potential_max_rub: int = Field(ge=0)
    items: list[RepairItem] = Field(default_factory=list)
    warnings: list[SafeText] = Field(default_factory=list)
    catalog_version: str


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
    verdict: DealVerdict
    reasons: list[SafeText]
    formula_version: str
