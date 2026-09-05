import re
from decimal import Decimal, ROUND_HALF_UP


def parse_rubles(text: str) -> int | None:
    """Parse one positive RUB amount; reject ranges and ambiguous digit sequences."""
    value=text.strip().replace("\u00a0"," ").removesuffix("₽").strip()
    if re.search(r"\d\s*[-–—]\s*\d",value): return None
    match=re.fullmatch(r"(\d{1,3}(?:[ ]\d{3})*|\d+)(?:[,.](\d{1,2}))?",value)
    if not match: return None
    amount=Decimal(match.group(1).replace(" ",""))
    if match.group(2): amount+=Decimal(match.group(2).ljust(2,"0"))/100
    return int(amount.quantize(Decimal("1"),rounding=ROUND_HALF_UP)) if amount>0 else None
