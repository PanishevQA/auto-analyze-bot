import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp

from config import YANDEX_GPT_CONFIG


class YandexGPTService:
    endpoint = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    def __init__(self, oauth_token: str, folder_id: str,
                 session: aiohttp.ClientSession) -> None:
        self.oauth_token = oauth_token
        self.folder_id = folder_id
        self.session = session

    async def complete_json(self, prompt: str, default: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(3):
            try:
                result = await self._request(prompt)
                return result
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError,
                    KeyError, TypeError, ValueError):
                if attempt == 2:
                    return default
        return default

    async def _request(self, prompt: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"OAuth {self.oauth_token}",
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json",
        }
        payload = {
            "modelUri": YANDEX_GPT_CONFIG["model_uri"],
            "completionOptions": {"stream": False, "temperature": YANDEX_GPT_CONFIG["temperature"],
                                  "maxTokens": YANDEX_GPT_CONFIG["max_tokens"]},
            "messages": [{"role": "user", "text": prompt}],
        }
        async with self.session.post(self.endpoint, headers=headers, json=payload,
                                     timeout=aiohttp.ClientTimeout(total=YANDEX_GPT_CONFIG["timeout"])) as response:
            response.raise_for_status()
            body = await response.json()
        text = body["result"]["alternatives"][0]["message"]["text"]
        return parse_json_response(text)

    async def from_template(self, name: str, values: dict[str, Any],
                            default: dict[str, Any]) -> dict[str, Any]:
        path = Path(__file__).parents[1] / "prompts" / name
        template = await asyncio.to_thread(path.read_text, encoding="utf-8")
        return await self.complete_json(template.format_map(values), default)


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("Ожидался JSON-объект")
    return value
