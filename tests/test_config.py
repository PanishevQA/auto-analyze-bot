from decimal import Decimal

import pytest

from config import Settings, _parse_owner_ids


def test_owner_ids_are_required_and_parsed(monkeypatch):
    assert _parse_owner_ids("1, 2,2") == frozenset({1, 2})
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test")
    monkeypatch.delenv("OWNER_TELEGRAM_IDS", raising=False)
    with pytest.raises(RuntimeError, match="OWNER_TELEGRAM_IDS"):
        Settings.from_env()


def test_decimal_financial_settings(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test")
    monkeypatch.setenv("OWNER_TELEGRAM_IDS", "123")
    monkeypatch.setenv("QUICK_SALE_COEFFICIENT", "0.91")
    monkeypatch.setenv("APIPOINT_TOKEN", "test")
    settings = Settings.from_env()
    assert settings.owner_telegram_ids == frozenset({123})
    assert settings.quick_sale_coefficient == Decimal("0.91")
