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
