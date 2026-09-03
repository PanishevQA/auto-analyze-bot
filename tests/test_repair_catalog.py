from decimal import Decimal

from schemas import DefectSeverity, DefectStatus, VisibleDefect
from services.repair_catalog import RepairCatalog


def defect(code: str, status: DefectStatus) -> VisibleDefect:
    return VisibleDefect(code=code, part="Дверь", severity=DefectSeverity.MINOR,
                         status=status, photo_numbers=[1], confidence=Decimal("0.9"))


def test_confirmed_potential_unknown_and_region_coefficient():
    catalog = RepairCatalog({
        "version": "v1", "region_coefficients": {"Москва": "1.20"},
        "items": {"scratch_minor": {"min_rub": 100, "likely_rub": 200, "max_rub": 300,
                                     "description": "Полировка", "requires_manual_check": False,
                                     "blocking_risk": True}},
    })
    result = catalog.estimate([
        defect("scratch_minor", DefectStatus.CONFIRMED),
        defect("scratch_minor", DefectStatus.POSSIBLE),
        defect("unknown_code", DefectStatus.CONFIRMED),
    ], "Москва")
    assert result.confirmed_likely_rub == 240
    assert result.potential_min_rub == 120
    assert result.potential_max_rub == 360
    assert result.confirmed_likely_rub != result.confirmed_likely_rub + result.potential_max_rub
    assert "unknown_code" in result.warnings[0]
    assert catalog.has_blocking_risk([defect("scratch_minor", DefectStatus.CONFIRMED)])
    assert not catalog.has_blocking_risk([defect("scratch_minor", DefectStatus.POSSIBLE)])
