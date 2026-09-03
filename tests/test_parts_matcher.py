from datetime import datetime,timezone
from schemas import MatchStatus,PartCondition,PartOffer,PartSearchQuery
from services.parts_matcher import infer_side_position,match_offer,sanitize_listing_text
from services.yandex_parts_agent import YandexPartsAgent

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
