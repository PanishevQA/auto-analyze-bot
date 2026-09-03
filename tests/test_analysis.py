from decimal import Decimal

from handlers.analysis import vehicle_from_fsm
from schemas import SourceMode


def test_vehicle_from_existing_fsm_data():
    vehicle = vehicle_from_fsm({
        "make": "Toyota", "model": "Camry", "year": 2018, "mileage_km": 100_000,
        "asking_price_rub": 2_000_000, "engine_volume_l": "2.5", "region":"Москва и МО",
        "seller_description": "Один владелец", "source_url":None,
    })
    assert vehicle.make == "Toyota"
    assert vehicle.model == "Camry"
    assert vehicle.engine_volume_l == Decimal("2.5")
    assert vehicle.source_mode is SourceMode.MANUAL
