from datetime import datetime,timezone
from decimal import Decimal
from types import SimpleNamespace
import pytest

from handlers.manual_parts import confirm
from schemas import (ConditionAssessment,Coverage,DefectSeverity,DefectStatus,MatchStatus,
    PartCondition,PartOffer,PartSearchQuery,RepairEstimate,VehicleSpec,VisibleDefect)
from services.deal_engine import DealEngine,DealSettings
from services.repair_catalog import RepairCatalog


@pytest.mark.asyncio
async def test_manual_confirmation_saves_without_market_and_keeps_defect_id():
    defect=VisibleDefect(defect_id="defect-left",code="headlamp",part="левая фара",
        severity=DefectSeverity.MEDIUM,status=DefectStatus.CONFIRMED,photo_numbers=[1],confidence=Decimal("0.9"))
    vehicle=VehicleSpec(make="Lada",model="Granta",year=2012,asking_price_rub=500000,region="x")
    query=PartSearchQuery(defect_id=defect.defect_id,make="Lada",model="Granta",year=2012,
        part_name="левая фара",region="x",condition=PartCondition.NEW)
    offers=[PartOffer(provider="manual",part_name="левая фара Lada Granta",condition=PartCondition.NEW,
        unit_price_rub=value,in_stock=True,offer_url=f"https://baza.drom.ru/{value}.html",
        fetched_at=datetime.now(timezone.utc),match_status=MatchStatus.EXACT,match_confidence=Decimal(".9"))
        for value in (10000,12000,14000)]
    old={"id":1,"car_data":vehicle.model_dump(mode="json"),"market_data":{},
        "repair_estimate":RepairEstimate(confirmed_min_rub=0,confirmed_likely_rub=0,confirmed_max_rub=0,
            potential_min_rub=0,potential_max_rub=0,catalog_version="v").model_dump(mode="json"),
        "condition_data":ConditionAssessment(coverage=Coverage.FULL,defects=[defect]).model_dump(mode="json"),
        "parts_data":[]}
    class DB:
        saved=None
        async def get_calculation_by_id(self,*args): return old
        async def complete_analysis(self,calc_id,**values): self.saved=values
    class State:
        async def get_data(self): return {"manual_calc_id":1,"manual_query":query.model_dump(mode="json"),
            "manual_offers":[o.model_dump(mode="json") for o in offers]}
        async def clear(self): pass
    class Message:
        async def answer(self,*args,**kwargs): pass
    class Callback:
        from_user=SimpleNamespace(id=7); message=Message()
        async def answer(self,*args,**kwargs): pass
    class Agent:
        async def classify_offers(self,*args): raise RuntimeError("offline")
    db=DB(); engine=DealEngine(DealSettings(Decimal(".92"),5000,10000,40000,10000))
    await confirm(Callback(),State(),db,engine,RepairCatalog({"version":"v","items":{}}),
        SimpleNamespace(drom_baza_start_url="https://baza.drom.ru/sell_spare_parts/",parts_min_matched_offers=3),Agent())
    assert db.saved["parts_data"][0]["defect_id"]=="defect-left"
    assert db.saved["scores"]["deal_result"]["verdict"]=="NO_RESULT"
    assert db.saved["scores"]["deal_result"]["economics_complete"] is False
