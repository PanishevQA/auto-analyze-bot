import json
from pathlib import Path
import httpx
import pytest
from schemas import Coverage, PhotoReference, VehicleSpec
from services.yandex_vision import YandexVisionClient

def condition(extra=None):
    value={"coverage":"LIMITED","body_score":80,"interior_score":None,"tires_score":None,
           "defects":[{"code":"scratch_minor","part":"дверь","severity":"MINOR",
           "status":"CONFIRMED","photo_numbers":[1],"confidence":"0.9","comment":"видно"}],
           "limitations":["нет правого бока"],"inspection_checklist":[],"model_uri":"x","prompt_version":"v"}
    if extra: value.update(extra)
    return value

@pytest.mark.asyncio
async def test_payload_numbering_and_valid_json(tmp_path:Path):
    photo=tmp_path/"1.jpg"; photo.write_bytes(b"jpeg")
    def handler(request):
        body=json.loads(request.content); assert body["model"]=="gpt://qwen"
        texts=[x.get("text") for x in body["input"][0]["content"] if x["type"]=="input_text"]
        assert "Фотография #1" in texts
        return httpx.Response(200,json={"output_text":json.dumps(condition()),"usage":{"x":1}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await YandexVisionClient(client,endpoint="https://ai.test/responses",api_key="k",
            model_uri="gpt://qwen",prompt_version="v1",defect_codes=["scratch_minor"]).assess(
            VehicleSpec(make="Lada",model="Vesta",year=2020,asking_price_rub=1,region="x"),
            [PhotoReference(telegram_file_id="1",order_number=1,mime_type="image/jpeg")],[photo],"a")
    assert result.coverage is Coverage.LIMITED and result.defects[0].photo_numbers==[1]

@pytest.mark.asyncio
async def test_invalid_then_one_repair_and_financial_field_rejected(tmp_path:Path):
    photo=tmp_path/"1.jpg"; photo.write_bytes(b"x"); calls=0
    def handler(request):
        nonlocal calls; calls+=1
        output="broken" if calls==1 else json.dumps(condition({"market_price":100}))
        return httpx.Response(200,json={"output_text":output})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await YandexVisionClient(client,endpoint="https://x",api_key="k",model_uri="m",
            prompt_version="v",defect_codes=[]).assess(VehicleSpec(make="a",model="b",year=2020,
            asking_price_rub=1,region="r"),[PhotoReference(telegram_file_id="1",order_number=1,
            mime_type="image/jpeg")],[photo],"a")
    assert calls==2 and result.coverage is Coverage.UNAVAILABLE

@pytest.mark.asyncio
async def test_no_photos_unavailable():
    async with httpx.AsyncClient() as client:
        result=await YandexVisionClient(client,endpoint=None,api_key=None,model_uri=None,
            prompt_version="v",defect_codes=[]).assess(VehicleSpec(make="a",model="b",year=2020,
            asking_price_rub=1,region="r"),[],[],"a")
    assert result.coverage is Coverage.UNAVAILABLE
