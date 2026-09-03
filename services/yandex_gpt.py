import asyncio
import json
import logging
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

import aiohttp

from config import YANDEX_GPT_CONFIG

logger = logging.getLogger(__name__)


class YandexGPTError(RuntimeError):
    """Yandex Cloud не вернул пригодный JSON после повторных попыток."""


class YandexGPTService:
    iam_endpoint = "https://iam.api.cloud.yandex.net/iam/v1/tokens"

    def __init__(self, folder_id: str, session: aiohttp.ClientSession, *,
                 api_key: str | None = None, oauth_token: str | None = None) -> None:
        if not api_key and not oauth_token:
            raise ValueError("Нужен Yandex API key или OAuth token")
        self.api_key = api_key
        self.oauth_token = oauth_token
        self.folder_id = folder_id
        self.session = session
        self._iam_token: str | None = None
        self._iam_token_valid_until = 0.0
        self._token_lock = asyncio.Lock()

    async def complete_json(self, prompt: str, default: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
        last_error: Exception | None = None
        request_id = uuid4().hex[:12]
        for attempt in range(3):
            try:
                logger.info(
                    "Запрос YandexGPT id=%s, попытка=%s/3, endpoint=%s, model=%s",
                    request_id, attempt + 1, YANDEX_GPT_CONFIG["endpoint"],
                    YANDEX_GPT_CONFIG["model_uri"],
                )
                result = await self._request(prompt, request_id)
                logger.info("Ответ YandexGPT успешно получен id=%s", request_id)
                return result
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError,
                    KeyError, TypeError, ValueError) as error:
                last_error = error
                logger.warning("Ошибка YandexGPT, попытка %s/3: %s", attempt + 1, error)
        if strict:
            if isinstance(last_error, asyncio.TimeoutError):
                raise last_error
            raise YandexGPTError("Не удалось получить данные от YandexGPT") from last_error
        return default

    async def _request(self, prompt: str, request_id: str) -> dict[str, Any]:
        authorization = await self._authorization()
        headers = {
            "Authorization": authorization,
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json",
        }
        payload = {
            "model": YANDEX_GPT_CONFIG["model_uri"],
            "temperature": YANDEX_GPT_CONFIG["temperature"],
            "max_tokens": YANDEX_GPT_CONFIG["max_tokens"],
            "messages": [{"role": "user", "content": prompt}],
        }
        # OpenAI-совместимый endpoint используется напрямую через aiohttp; библиотека
        # openai намеренно не подключается, чтобы сохранить утвержденный стек проекта.
        async with self.session.post(YANDEX_GPT_CONFIG["endpoint"], headers=headers, json=payload,
                                     timeout=aiohttp.ClientTimeout(total=YANDEX_GPT_CONFIG["timeout"])) as response:
            response.raise_for_status()
            body = await response.json()
            logger.info(
                "YandexGPT HTTP id=%s, status=%s, usage=%s",
                request_id, response.status, body.get("usage", "не передано"),
            )
        text = body["choices"][0]["message"]["content"]
        return parse_json_response(text)

    async def _authorization(self) -> str:
        if self.api_key:
            return f"Api-Key {self.api_key}"
        return f"Bearer {await self._get_iam_token()}"

    async def _get_iam_token(self) -> str:
        if not self.oauth_token:
            raise ValueError("OAuth token не задан")
        if self._iam_token and time.monotonic() < self._iam_token_valid_until:
            return self._iam_token
        async with self._token_lock:
            if self._iam_token and time.monotonic() < self._iam_token_valid_until:
                return self._iam_token
            async with self.session.post(
                self.iam_endpoint,
                json={"yandexPassportOauthToken": self.oauth_token},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                response.raise_for_status()
                payload = await response.json()
            self._iam_token = str(payload["iamToken"])
            # IAM-токен живет до 12 часов; обновляем заранее, не логируя секрет.
            self._iam_token_valid_until = time.monotonic() + 10 * 60 * 60
            return self._iam_token

    async def from_template(self, name: str, values: dict[str, Any],
                            default: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
        path = Path(__file__).parents[1] / "prompts" / name
        template = await asyncio.to_thread(path.read_text, encoding="utf-8")
        return await self.complete_json(template.format_map(values), default, strict=strict)


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("Ожидался JSON-объект")
    return value
