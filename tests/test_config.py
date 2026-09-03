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

def test_authorized_browser_requires_permission(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN","test"); monkeypatch.setenv("OWNER_TELEGRAM_IDS","1")
    monkeypatch.setenv("APIPOINT_TOKEN","test"); monkeypatch.setenv("PARTS_SEARCH_MODE","AUTHORIZED_DROM_BROWSER")
    monkeypatch.setenv("DROM_BAZA_PERMISSION_CONFIRMED","false")
    with pytest.raises(RuntimeError,match="разрешения правообладателя"): Settings.from_env()

def test_drom_start_url_allowlist(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN","test"); monkeypatch.setenv("OWNER_TELEGRAM_IDS","1")
    monkeypatch.setenv("APIPOINT_TOKEN","test"); monkeypatch.setenv("DROM_BAZA_START_URL","https://evil.test/")
    with pytest.raises(RuntimeError,match="baza.drom.ru"): Settings.from_env()
