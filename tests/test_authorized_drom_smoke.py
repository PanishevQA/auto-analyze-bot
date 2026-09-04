import os
import pytest

from config import Settings
from schemas import PartCondition, PartSearchQuery
from services.browser_parts_provider import BrowserPartsProvider


@pytest.mark.authorized_drom_smoke
@pytest.mark.asyncio
async def test_authorized_drom_smoke_one_search():
    if os.getenv("RUN_AUTHORIZED_DROM_SMOKE") != "true":
        pytest.skip("set RUN_AUTHORIZED_DROM_SMOKE=true for the manual authorized smoke test")
    if os.getenv("DROM_BAZA_PERMISSION_CONFIRMED") != "true":
        pytest.skip("the rightsholder permission must be confirmed explicitly")
    provider=BrowserPartsProvider(os.getenv("DROM_BAZA_START_URL", "https://baza.drom.ru/novosibirskaya-obl/sell_spare_parts/"),
        max_offers=1,min_offers=1)
    try:
        result=await provider.search(PartSearchQuery(make="Lada",model="Granta",year=2012,
            part_name="фара",search_phrase="фара Lada Granta 2012",region="Новосибирск",condition=PartCondition.USED))
        assert result.status.value in {"READY","INSUFFICIENT_DATA","BLOCKED","UNAVAILABLE","ERROR"}
    finally:
        await provider.close()
