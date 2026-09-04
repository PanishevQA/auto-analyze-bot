from decimal import Decimal

from schemas import (DefectSeverity, DefectStatus, PartCondition, VehicleSpec, VisibleDefect)
from services.yandex_parts_agent import YandexPartsAgent
from utils.keyboards import HISTORY, NEW_ANALYSIS, main_menu


def test_main_menu_exposes_primary_actions():
    labels = [button.text for row in main_menu().keyboard for button in row]
    assert NEW_ANALYSIS in labels
    assert HISTORY in labels


def test_equal_defect_codes_keep_independent_ids():
    defects = [VisibleDefect(code="headlamp", part=side, severity=DefectSeverity.MEDIUM,
        status=DefectStatus.CONFIRMED, photo_numbers=[index], confidence=Decimal("0.9"))
        for index, side in enumerate(("левая фара", "правая фара"), 1)]
    assert defects[0].defect_id != defects[1].defect_id


def test_parts_plan_contains_vehicle_and_not_invented_oem():
    car=VehicleSpec(make="Lada",model="Granta",year=2012,asking_price_rub=1,region="Новосибирск")
    plan=YandexPartsAgent().build_plan(car,"фара","левая","передняя",PartCondition.USED)
    assert plan.query == "передняя левая фара Lada Granta 2012"
    assert plan.oem_number is None

import pytest


@pytest.mark.asyncio
async def test_yandex_parts_agent_posts_and_validates_structured_plan():
    class Vision:
        endpoint="https://llm.api.cloud.yandex.net/v1/responses"
        model_uri="gpt://folder/model"
        def __init__(self): self.payload=None
        async def _post(self,payload):
            self.payload=payload
            return ('{"query":"фара Lada Granta 2012","normalized_part_name":"фара",'
                    '"required_tokens":[],"optional_tokens":[],"exclude_tokens":[],'
                    '"oem_number":null,"make":"Lada","model":"Granta","year":2012,'
                    '"generation":null,"side":null,"position":null,"condition":"USED"}',{})
    vision=Vision(); car=VehicleSpec(make="Lada",model="Granta",year=2012,asking_price_rub=1,region="x")
    plan=await YandexPartsAgent(vision).create_plan(car,"фара",None,None,PartCondition.USED)
    assert plan.normalized_part_name == "фара"
    assert vision.payload["text"]["format"]["strict"] is True

@pytest.mark.asyncio
async def test_yandex_parts_agent_classifies_batch_with_match_prompt():
    class Vision:
        endpoint="https://llm.api.cloud.yandex.net/v1/responses"; model_uri="gpt://folder/model"; max_retries=0
        def __init__(self): self.payload=None
        async def _post(self,payload):
            self.payload=payload
            return ('{"matches":[{"offer_index":0,"status":"EXACT","confidence":0.94,'
                    '"reasons":["совпали марка и модель"]}]}',{})
    from datetime import datetime,timezone
    from schemas import MatchStatus,PartOffer,PartSearchQuery
    vision=Vision(); agent=YandexPartsAgent(vision,max_retries=1)
    car=VehicleSpec(make="Lada",model="Granta",year=2012,asking_price_rub=1,region="x")
    query=PartSearchQuery(make="Lada",model="Granta",year=2012,part_name="фара",region="x",condition=PartCondition.USED)
    offers=[PartOffer(provider="fixture",part_name="<b>фара Lada Granta</b>",condition=PartCondition.USED,
        unit_price_rub=100,in_stock=True,fetched_at=datetime.now(timezone.utc))]
    matched,metadata=await agent.classify_offers(car,query,offers)
    assert matched[0].match_status is MatchStatus.EXACT
    assert metadata["matching_source"] == "YANDEX_AI"
    assert "<b>" not in vision.payload["input"][0]["content"][0]["text"]
    assert vision.max_retries == 0
