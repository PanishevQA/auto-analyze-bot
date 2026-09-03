import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp


DEFAULT_MARKET = {"region_avg": 0, "rf_avg": 0, "quick": 0, "min": 0, "max": 0}


class MarketService:
    def __init__(self, session: aiohttp.ClientSession, api_url: str | None = None,
                 api_token: str | None = None) -> None:
        self.session, self.api_url, self.api_token = session, api_url, api_token

    async def prices(self, car_model: str, year: int, region: str) -> dict[str, int]:
        data: dict[str, Any] | None = None
        if self.api_url:
            try:
                headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}
                async with self.session.get(
                    self.api_url, params={"model": car_model, "year": year, "region": region},
                    headers=headers, timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                data = None
        if data is None:
            data = await self._fallback(car_model, year)
        result = {key: max(0, int(data.get(key, 0))) for key in DEFAULT_MARKET}
        if region == "Весь РФ":
            result["region_avg"] = result["rf_avg"]
        return result

    async def _fallback(self, car_model: str, year: int) -> dict[str, Any]:
        path = Path(__file__).parents[1] / "config" / "fallback_prices.json"
        raw = await asyncio.to_thread(path.read_text, encoding="utf-8")
        records = json.loads(raw)
        model = next((name for name in records if name.casefold() == car_model.casefold()), None)
        return records.get(model, {}).get(str(year), DEFAULT_MARKET)

