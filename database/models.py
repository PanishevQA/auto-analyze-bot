from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class User:
    id: int
    telegram_id: int
    region: str
    created_at: datetime


@dataclass(slots=True)
class Calculation:
    user_id: int
    car_data: dict[str, Any]
    market_data: dict[str, Any]
    repair_estimate: dict[str, Any]
    scores: dict[str, Any]
    final_report: str

