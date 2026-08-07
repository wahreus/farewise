"""Domain models for FareWise optimization results."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

@dataclass(frozen=True)
class PaygSelection:
    """Selected PAYG period and its recorded cost."""
    start_date: date
    end_date: date
    cost: Decimal
    journey_count: int

    @property
    def total_cost(self) -> Decimal:
        """Return the total cost of the PAYG selection."""
        return self.cost

@dataclass(frozen=True)
class TravelcardSelection:
    """Selected Travelcard period and any outside PAYG usage."""
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
        """Return the Travelcard cost including outside PAYG."""
        return self.card_cost + self.outside_payg_cost

PaymentSelection = PaygSelection | TravelcardSelection

@dataclass(frozen=True)
class OptimizationResult:
    """Complete result of a FareWise fare optimization."""
    journey_start_date: date
    journey_end_date: date
    payg_total: Decimal
    optimized_total: Decimal
    selections: tuple[PaymentSelection, ...]
    warnings: tuple[str, ...] = ()

    @property
    def savings(self) -> Decimal:
        """Return the difference between recorded and optimized cost."""
        return self.payg_total - self.optimized_total

    @property
    def uses_travelcard(self) -> bool:
        """Return whether the strategy includes a Travelcard."""
        return any(isinstance(selection, TravelcardSelection)
                   for selection in self.selections)
