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
    """Selected Travelcard purchase."""

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
        """Return the Travelcard cost including attached outside PAYG."""

        return self.card_cost + self.outside_payg_cost


@dataclass(frozen=True)
class BusTramPassSelection:
    """Selected Bus & Tram Pass purchase."""

    product_name: str
    start_date: date
    end_date: date
    pass_cost: Decimal
    covered_journey_count: int

    @property
    def total_cost(self) -> Decimal:
        """Return the Bus & Tram Pass purchase cost."""

        return self.pass_cost


PaymentSelection = PaygSelection | TravelcardSelection | BusTramPassSelection


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

        return any(
            isinstance(selection, TravelcardSelection)
            for selection in self.selections
        )

    @property
    def uses_bus_tram_pass(self) -> bool:
        """Return whether the strategy includes a Bus & Tram Pass."""

        return any(
            isinstance(selection, BusTramPassSelection)
            for selection in self.selections
        )
