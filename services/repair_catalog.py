import asyncio
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
from typing import Any

from schemas import DefectStatus, RepairEstimate, RepairItem, VisibleDefect


class RepairCatalog:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.version = str(payload["version"])
        self.items = dict(payload["items"])
        self.region_coefficients = {
            name: Decimal(str(value)) for name, value in payload.get("region_coefficients", {}).items()
        }

    @classmethod
    async def load(cls, path: Path | None = None) -> "RepairCatalog":
        catalog_path = path or Path(__file__).parents[1] / "config" / "repair_catalog.json"
        raw = await asyncio.to_thread(catalog_path.read_text, encoding="utf-8")
        return cls(json.loads(raw))

    def estimate(self, defects: list[VisibleDefect], region: str) -> RepairEstimate:
        coefficient = self.region_coefficients.get(region, Decimal("1.00"))
        confirmed = [0, 0, 0]
        potential = [0, 0, 0]
        items: list[RepairItem] = []
        warnings: list[str] = []
        for defect in defects:
            entry = self.items.get(defect.code)
            if entry is None:
                warnings.append(f"Нет цены для кода {defect.code}; требуется ручная оценка")
                continue
            values = [self._money(entry[key], coefficient) for key in ("min_rub", "likely_rub", "max_rub")]
            target = confirmed if defect.status is DefectStatus.CONFIRMED else potential
            for index, value in enumerate(values):
                target[index] += value
            items.append(RepairItem(
                defect_code=defect.code, description=str(entry["description"]), status=defect.status,
                min_rub=values[0], likely_rub=values[1], max_rub=values[2],
                requires_manual_check=bool(entry.get("requires_manual_check", False)),
                operation=str(entry.get("operation", "REPAIR")),
                requires_part=bool(entry.get("requires_part", False)),
            ))
        return RepairEstimate(
            confirmed_min_rub=confirmed[0], confirmed_likely_rub=confirmed[1],
            confirmed_max_rub=confirmed[2], potential_min_rub=potential[0],
            potential_max_rub=potential[2], items=items, warnings=warnings,
            catalog_version=self.version,
            labor_likely_rub=confirmed[1], consumables_likely_rub=0,
        )

    def has_blocking_risk(self, defects: list[VisibleDefect]) -> bool:
        return any(defect.status is DefectStatus.CONFIRMED
                   and bool(self.items.get(defect.code, {}).get("blocking_risk", False))
                   for defect in defects)

    @staticmethod
    def _money(value: int, coefficient: Decimal) -> int:
        return int((Decimal(value) * coefficient).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
