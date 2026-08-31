import pytest

from utils.validators import *


@pytest.mark.parametrize("value", ["", "A"])
def test_model_invalid(value):
    with pytest.raises(ValueError): validate_car_model(value)


def test_all_validators():
    assert validate_car_model(" Toyota Camry ") == "Toyota Camry"
    assert validate_year("2027", current_year=2026) == 2027
    assert validate_mileage("0") == 0
    assert validate_mileage("500000") == 500000
    assert validate_engine("2.5 AT") == "2.5 AT"
    assert validate_price("10000") == 10000
    assert validate_issues("/skip") == "Не указаны"


@pytest.mark.parametrize("function,value", [
    (validate_year, "1989"), (validate_year, "abc"),
    (validate_mileage, "500001"), (validate_mileage, "1 000"),
    (validate_engine, "  "), (validate_price, "9999"),
    (validate_price, "50000001"),
])
def test_invalid(function, value):
    with pytest.raises(ValueError): function(value)

