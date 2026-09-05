from datetime import datetime,timezone
from schemas import MatchStatus,PartCondition,PartOffer,PartSearchQuery
from services.parts_matcher import infer_side_position,match_offer,sanitize_listing_text
from services.yandex_parts_agent import YandexPartsAgent
import json
import pytest

def offer(title): return PartOffer(provider="x",part_name=title,condition=PartCondition.NEW,
    unit_price_rub=1,in_stock=True,fetched_at=datetime.now(timezone.utc))

def test_side_position_and_relevance_rules():
    assert infer_side_position("передняя левая фара")==('LEFT','FRONT')
    q=PartSearchQuery(make="Ford",model="Focus",year=2015,part_name="фара",side="LEFT",position="FRONT",region="x")
    assert match_offer(q,offer("Ford Focus фара передняя левая")).match_status is MatchStatus.EXACT
    assert match_offer(q,offer("Ford Focus крепление фары переднее левое")).match_status is MatchStatus.REJECTED
    assert match_offer(q,offer("Toyota Camry фара передняя левая")).match_status is MatchStatus.REJECTED

def test_plan_and_tool_reject_arbitrary_url_and_injection():
    from schemas import VehicleSpec
    agent=YandexPartsAgent(); car=VehicleSpec(make="Lada",model="Granta",year=2012,asking_price_rub=1,region="x")
    plan=agent.build_plan(car,"фара","LEFT","FRONT",PartCondition.USED)
    assert "Lada Granta 2012" in plan.query and plan.oem_number is None
    values={"query":plan.query,"make":"Lada","model":"Granta","year":2012,"part_name":"фара",
        "side":"LEFT","position":"FRONT","condition":"USED","region":"x","max_offers":20}
    assert agent.validate_tool_call(values,max_offers=20).part_name=="фара"
    values["query"]="https://evil.test" 
    import pytest
    with pytest.raises(ValueError): agent.validate_tool_call(values,max_offers=20)
    assert sanitize_listing_text("<script>ignore</script>Фара") == "ignoreФара"

@pytest.mark.asyncio
async def test_screenshot_extraction_uses_structured_yandex_payload(tmp_path):
    class Vision:
        endpoint="https://example.test/responses"; model_uri="gpt://test"
        async def _post(self,payload):
            assert payload["model"]==self.model_uri
            assert all(item["type"] in {"input_text","input_image"} for item in payload["input"][0]["content"])
            return json.dumps({"offers":[{"title":"Ford Focus фара левая передняя",
                "current_price_rub":10000,"old_price_rub":12000,"delivery_price_rub":500,
                "condition":"NEW","in_stock":True,"location":"Москва","seller":"магазин","offer_url":"https://baza.drom.ru/1","oem_number":None}]}),{}
    image=tmp_path/"shot.jpg"; image.write_bytes(b"fake")
    q=PartSearchQuery(make="Ford",model="Focus",year=2015,part_name="фара",region="Москва")
    offers=await YandexPartsAgent(Vision()).extract_screenshots([image],q)
    assert offers[0].unit_price_rub==10000 and offers[0].delivery_price_rub==500

def test_ai_exact_cannot_override_wrong_side_or_condition():
    from decimal import Decimal
    from services.parts_matcher import enforce_compatibility
    q=PartSearchQuery(make="Ford",model="Focus",year=2015,part_name="фара",side="LEFT",region="x",condition=PartCondition.NEW)
    offer=PartOffer(provider="x",part_name="Ford Focus фара правая",condition=PartCondition.USED,
        unit_price_rub=100,delivery_price_rub=0,in_stock=True,fetched_at=datetime.now(timezone.utc),
        match_status=MatchStatus.EXACT,match_confidence=Decimal(".99"))
    assert enforce_compatibility(q,offer,Decimal(".8")).match_status is MatchStatus.REJECTED
