from dataclasses import dataclass
from datetime import date
from decimal import Decimal

@dataclass(frozen=True)
class PaygSelection:
    start_date: date
    end_date: date
    cost: Decimal
    journey_count: int

    @property
    def total_cost(self) -> Decimal:
        return self.cost

@dataclass(frozen=True)
class TravelcardSelection:
    product_name: str
    zone_name: str
    max_zone: int
    start_date: date
    end_date: date
    card_cost: Decimal
    outside_payg_cost: Decimal
    covered_journey_count: int
    uncovered_journey_count: int

    @property
    def total_cost(self) -> Decimal:
        return self.card_cost + self.outside_payg_cost

PaymentSelection = PaygSelection | TravelcardSelection

@dataclass(frozen=True)
class OptimizationResult:
    journey_start_date: date
    journey_end_date: date
    payg_total: Decimal
    optimized_total: Decimal
    selections: tuple[PaymentSelection, ...]
    warnings: tuple[str, ...] = ()

    @property
    def savings(self) -> Decimal:
        return self.payg_total - self.optimized_total

    @property
    def uses_travelcard(self) -> bool:
        return any(isinstance(selection, TravelcardSelection)
                   for selection in self.selections)
