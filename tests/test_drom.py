import pytest
from services.drom import InvalidDromUrl, ManualDromAdapter
from schemas import SourceMode

@pytest.mark.asyncio
async def test_manual_drom_is_validation_only():
    value = await ManualDromAdapter().validate("https://auto.drom.ru/test/12345.html?utm_source=x&a=1")
    assert value.source_mode is SourceMode.MANUAL
    assert value.listing_id == "12345"
    assert "utm_" not in value.source_url and "a=1" in value.source_url

@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["http://drom.ru/1", "https://evil.test/1",
    "https://drom.ru.attacker.example/1", "https://u:p@drom.ru/1", "https://drom.ru:444/1",
    "https://127.0.0.1/1"])
async def test_invalid_drom_urls(url):
    with pytest.raises(InvalidDromUrl): await ManualDromAdapter().validate(url)
