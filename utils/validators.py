from datetime import datetime


def validate_car_model(value: str) -> str:
    value = value.strip()
    if len(value) < 2:
        raise ValueError("Укажите марку и модель (минимум 2 символа).")
    return value


def _integer(value: str, name: str, minimum: int, maximum: int) -> int:
    cleaned = value.strip()
    if not cleaned.isdigit():
        raise ValueError(f"{name}: введите только цифры.")
    number = int(cleaned)
    if not minimum <= number <= maximum:
        raise ValueError(f"{name}: допустимо от {minimum:,} до {maximum:,}.".replace(",", " "))
    return number


def validate_year(value: str, current_year: int | None = None) -> int:
    return _integer(value, "Год", 1990, (current_year or datetime.now().year) + 1)


def validate_mileage(value: str) -> int:
    return _integer(value, "Пробег", 0, 500_000)


def validate_engine(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Укажите двигатель и КПП.")
    return value


def validate_price(value: str) -> int:
    return _integer(value, "Цена", 10_000, 50_000_000)


def validate_issues(value: str | None) -> str:
    value = (value or "").strip()
    return "Не указаны" if value.lower() in {"", "-", "/skip", "пропустить"} else value

