import asyncio
import base64
import json
import logging
from pathlib import Path
import time
from typing import Any

import httpx
from pydantic import ValidationError

from schemas import ConditionAssessment, Coverage, PhotoReference, VehicleSpec

logger = logging.getLogger(__name__)


class VisionNotConfigured(RuntimeError): pass


class YandexVisionClient:
    def __init__(self, client: httpx.AsyncClient, *, endpoint: str | None, api_key: str | None,
                 model_uri: str | None, prompt_version: str, defect_codes: list[str]) -> None:
        self.client, self.endpoint, self.api_key, self.model_uri = client, endpoint, api_key, model_uri
        self.prompt_version, self.defect_codes = prompt_version, defect_codes
        self.timeout: httpx.Timeout | None = None
        self.max_retries = 1

    async def assess(self, vehicle: VehicleSpec, photos: list[PhotoReference],
                     paths: list[Path], analysis_id: str) -> ConditionAssessment:
        if not photos:
            return self.unavailable("Состояние по фотографиям не анализировалось")
        if not self.endpoint or not self.api_key or not self.model_uri:
            return self.unavailable("Yandex Vision не настроен")
        started = time.monotonic()
        prompt = await self._prompt(vehicle)
        payload = await self.build_payload(prompt, photos, paths)
        try:
            text, usage = await self._post(payload)
            try:
                result = self._validate(text)
            except (json.JSONDecodeError, ValidationError, ValueError):
                repair = self.build_repair_payload(text)
                fixed, usage = await self._post(repair)
                result = self._validate(fixed)
            logger.info("Vision analysis_id=%s model=%s prompt=%s duration=%.3f usage=%s",
                        analysis_id, self.model_uri, self.prompt_version,
                        time.monotonic() - started, usage)
            return result.model_copy(update={"model_uri": self.model_uri,
                                             "prompt_version": self.prompt_version})
        except (httpx.HTTPError, json.JSONDecodeError, ValidationError, ValueError) as error:
            logger.warning("Vision analysis_id=%s status=UNAVAILABLE error=%s duration=%.3f",
                           analysis_id, type(error).__name__, time.monotonic() - started)
            return self.unavailable("Vision-анализ недоступен или вернул невалидный JSON")

    async def _prompt(self, vehicle: VehicleSpec) -> str:
        template = await asyncio.to_thread((Path(__file__).parents[1] / "prompts" /
                                            "vehicle_condition_v1.txt").read_text, encoding="utf-8")
        return template.format(defect_codes=", ".join(self.defect_codes),
            make=vehicle.make, model=vehicle.model, year=vehicle.year,
            generation=vehicle.generation or "неизвестно", mileage_km=vehicle.mileage_km or "неизвестно",
            seller_description=vehicle.seller_description or "не указано")

    async def build_payload(self, prompt: str, photos: list[PhotoReference], paths: list[Path]) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        for reference, path in zip(photos, paths, strict=True):
            raw = await asyncio.to_thread(path.read_bytes)
            encoded = base64.b64encode(raw).decode()
            content.append({"type": "input_text", "text": f"Фотография #{reference.order_number}"})
            content.append({"type": "input_image", "image_url": f"data:{reference.mime_type};base64,{encoded}"})
        return {"model": self.model_uri, "input": [{"role": "user", "content": content}],
                "text": {"format": {"type": "json_schema", "name": "condition_assessment",
                                      "schema": ConditionAssessment.model_json_schema(), "strict": True}}}

    def build_repair_payload(self, broken: str) -> dict[str, Any]:
        return {"model": self.model_uri, "input": [{"role": "user", "content": [{"type": "input_text",
            "text": "Исправь только синтаксис/схему JSON, не добавляя фактов:\n" + broken[:20_000]}]}],
            "text": {"format": {"type": "json_schema", "name": "condition_assessment",
                                  "schema": ConditionAssessment.model_json_schema(), "strict": True}}}

    async def _post(self, payload: dict[str, Any], *, max_retries: int | None = None) -> tuple[str, Any]:
        response = None
        retries=self.max_retries if max_retries is None else max_retries
        for attempt in range(retries + 1):
            try:
                response = await self.client.post(self.endpoint, json=payload,
                    headers={"Authorization": f"Api-Key {self.api_key}"}, timeout=self.timeout)
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status(); break
            except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
                temporary = isinstance(error, httpx.TimeoutException) or error.response.status_code == 429 or error.response.status_code >= 500
                if not temporary or attempt >= retries: raise
                await asyncio.sleep(0)
        body = response.json()
        text = body.get("output_text")
        if not isinstance(text, str):
            try: text = body["output"][0]["content"][0]["text"]
            except (KeyError, IndexError, TypeError) as error: raise ValueError("Нет output_text") from error
        return text, body.get("usage")

    def _validate(self, text: str) -> ConditionAssessment:
        value = json.loads(text)
        value.pop("raw_payload", None)
        validated = ConditionAssessment.model_validate(value)
        return validated.model_copy(update={"raw_payload": value})

    def unavailable(self, reason: str) -> ConditionAssessment:
        return ConditionAssessment(coverage=Coverage.UNAVAILABLE, defects=[], limitations=[reason],
            inspection_checklist=[], model_uri=self.model_uri or "not-configured",
            prompt_version=self.prompt_version)
