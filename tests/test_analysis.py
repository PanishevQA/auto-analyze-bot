from decimal import Decimal

from handlers.analysis import vehicle_from_fsm
from schemas import SourceMode


def test_vehicle_from_existing_fsm_data():
    vehicle = vehicle_from_fsm({
        "car_model": "Toyota Camry", "year": 2018, "mileage": 100_000,
        "price": 2_000_000, "engine": "2.5 AT",
        "listing_description": "Один владелец",
    }, "Москва и МО")
    assert vehicle.make == "Toyota"
    assert vehicle.model == "Camry"
    assert vehicle.engine_volume_l == Decimal("2.5")
    assert vehicle.source_mode is SourceMode.MANUAL
