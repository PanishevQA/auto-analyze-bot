from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from schemas import (Coverage, DealResult, DealVerdict, MarketConfidence,
                     MarketEstimate, RepairEstimate)

FORMULA_VERSION = "deal-engine-v1"


@dataclass(frozen=True, slots=True)
class DealSettings:
    quick_sale_coefficient: Decimal
    fixed_expenses_rub: int
    risk_reserve_rub: int
    target_profit_rub: int
    excellent_price_margin_rub: int

    def __post_init__(self) -> None:
        if not Decimal("0") < self.quick_sale_coefficient <= Decimal("1"):
            raise ValueError("Коэффициент быстрой продажи должен быть в диапазоне (0, 1]")
        if any(value < 0 for value in (
            self.fixed_expenses_rub, self.risk_reserve_rub,
            self.target_profit_rub, self.excellent_price_margin_rub,
        )):
            raise ValueError("Финансовые настройки не могут быть отрицательными")


class DealEngine:
    def __init__(self, settings: DealSettings) -> None:
        self.settings = settings

    def calculate(
        self, *, asking_price_rub: int, market: MarketEstimate | None,
        repairs: RepairEstimate, coverage: Coverage = Coverage.UNAVAILABLE,
        has_blocking_risk: bool = False, parts_total_rub: int = 0,
        parts_complete: bool = True,
    ) -> DealResult:
        if asking_price_rub <= 0:
            raise ValueError("Цена продавца должна быть положительной")
        if market is None:
            return DealResult(
                quick_sale_price_rub=0, repair_likely_rub=repairs.confirmed_likely_rub,
                fixed_expenses_rub=self.settings.fixed_expenses_rub,
                risk_reserve_rub=self.settings.risk_reserve_rub,
                total_investment_rub=asking_price_rub + repairs.confirmed_likely_rub
                + self.settings.fixed_expenses_rub + self.settings.risk_reserve_rub,
                expected_profit_rub=0, roi_percent=Decimal("0"),
                break_even_buy_price_rub=0, max_buy_price_rub=0,
                excellent_buy_price_rub=0, required_discount_rub=0,
                target_profit_rub=self.settings.target_profit_rub,
                verdict=DealVerdict.NO_RESULT,
                reasons=["Рыночная оценка APIpoint или MANUAL отсутствует"],
                formula_version=FORMULA_VERSION,
                economics_complete=False,
            )

        quick = int((Decimal(market.market_price_rub) * self.settings.quick_sale_coefficient)
                    .quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        repair = repairs.confirmed_likely_rub + parts_total_rub
        total = asking_price_rub + repair + self.settings.fixed_expenses_rub + self.settings.risk_reserve_rub
        profit = quick - total
        roi = (Decimal(profit) / Decimal(total) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        # Все цены покупки, которым запрещено быть отрицательными, ограничиваются здесь.
        break_even = max(0, quick - repair - self.settings.fixed_expenses_rub - self.settings.risk_reserve_rub)
        max_buy = max(0, break_even - self.settings.target_profit_rub)
        excellent = max(0, max_buy - self.settings.excellent_price_margin_rub)
        discount = max(0, asking_price_rub - max_buy)

        possible = repairs.potential_max_rub > 0
        reasons: list[str] = []
        if has_blocking_risk:
            verdict = DealVerdict.PASS
            reasons.append("Подтвержден критический риск")
        elif asking_price_rub > break_even or profit < 0:
            verdict = DealVerdict.PASS
            reasons.append(f"Цена продавца выше безубыточной цены {break_even} ₽")
        elif (asking_price_rub <= max_buy and coverage is Coverage.FULL and not possible and parts_complete
              and market.confidence is MarketConfidence.HIGH):
            verdict = DealVerdict.BUY
            reasons.append(f"Цена не превышает целевую максимальную цену {max_buy} ₽")
        else:
            verdict = DealVerdict.WATCH
            if asking_price_rub > max_buy:
                reasons.append(f"Для целевой прибыли требуется цена не выше {max_buy} ₽")
            if coverage is not Coverage.FULL:
                reasons.append("Фотографии дают ограниченную или недоступную оценку состояния")
            if possible:
                reasons.append("Есть возможные дефекты, требующие очной проверки")
            if market.confidence is not MarketConfidence.HIGH:
                reasons.append(f"Уверенность рынка {market.confidence.value}: проверьте аналоги вручную")
            if not parts_complete:
                reasons.append("Актуальные цены необходимых запчастей не получены; BUY недоступен")

        return DealResult(
            quick_sale_price_rub=quick, repair_likely_rub=repair,
            fixed_expenses_rub=self.settings.fixed_expenses_rub,
            risk_reserve_rub=self.settings.risk_reserve_rub,
            total_investment_rub=total, expected_profit_rub=profit, roi_percent=roi,
            break_even_buy_price_rub=break_even, max_buy_price_rub=max_buy,
            excellent_buy_price_rub=excellent, required_discount_rub=discount,
            target_profit_rub=self.settings.target_profit_rub,
            verdict=verdict, reasons=reasons, formula_version=FORMULA_VERSION,
            economics_complete=parts_complete,
        )
