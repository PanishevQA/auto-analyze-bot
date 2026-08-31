import json

import pytest

from services.link_generator import generate_search_links
from services.market_api import MarketService
from config import YANDEXGPT_ENDPOINT, YANDEXGPT_MODEL_URI
from services.yandex_gpt import YandexGPTService, parse_json_response


def test_search_links_are_search_pages_and_encoded():
    links = generate_search_links("цепь ГРМ Toyota")
    assert set(links) == {"auto_ru", "drom", "exist"}
    assert all("%D1" in link for link in links.values())
    assert all("search" in link.lower() or "query=" in link or "Price/" in link for link in links.values())


def test_parse_json_plain_and_fenced():
    assert parse_json_response('{"x": 1}') == {"x": 1}
    assert parse_json_response('```json\n{"x": 1}\n```') == {"x": 1}
    with pytest.raises((json.JSONDecodeError, ValueError)):
        parse_json_response("не JSON")


@pytest.mark.asyncio
async def test_yandex_api_key_auth_and_endpoint():
    service = YandexGPTService("folder", session=None, api_key="secret")
    assert await service._authorization() == "Api-Key secret"
    assert YANDEXGPT_ENDPOINT == "https://ai.api.cloud.yandex.net/v1/chat/completions"
    assert YANDEXGPT_MODEL_URI.endswith("/yandexgpt-5.1/latest")


@pytest.mark.asyncio
async def test_market_fallback_and_rf_rule():
    service = MarketService(session=None)
    result = await service.prices("Toyota Camry", 2014, "Весь РФ")
    assert result["region_avg"] == result["rf_avg"] == 1_650_000
    assert result["quick"] == 1_520_000


@pytest.mark.asyncio
async def test_lada_market_fallback_is_not_zero():
    service = MarketService(session=None)
    result = await service.prices("Лада 2114 Самара", 2011, "Новосибирск и НО")
    assert result["region_avg"] == 190_000
    assert result["quick"] == 180_000
