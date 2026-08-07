"""Tests for optimization result and selection properties."""

from datetime import date
from decimal import Decimal

from src.results import (OptimizationResult,
                         PaygSelection,
                         TravelcardSelection)


def payg_selection() -> PaygSelection:
    """Build a representative PAYG selection for result tests."""
    return PaygSelection(start_date=date(2026, 3, 1),
                         end_date=date(2026, 3, 1),
                         cost=Decimal("5.60"),
                         journey_count=2)


def travelcard_selection() -> TravelcardSelection:
    """Build a representative Travelcard selection for result tests."""
    return TravelcardSelection(product_name="7 Day",
                               zone_name="Zones 1-2",
                               max_zone=2,
                               start_date=date(2026, 3, 1),
                               end_date=date(2026, 3, 7),
                               card_cost=Decimal("44.70"),
                               outside_payg_cost=Decimal("2.80"),
                               covered_journey_count=10,
                               uncovered_journey_count=1)


def test_payg_selection_total_cost_returns_cost() -> None:
    """Verify that PAYG selection total cost returns cost."""
    assert payg_selection().total_cost == Decimal("5.60")


def test_travelcard_selection_total_cost_includes_outside_payg() -> None:
    """Verify that travelcard selection total cost includes outside PAYG."""
    assert travelcard_selection().total_cost == Decimal("47.50")


def test_optimization_result_savings_returns_difference() -> None:
    """Verify that optimization result savings returns difference."""
    result = OptimizationResult(
        journey_start_date=date(2026, 3, 1),
        journey_end_date=date(2026, 3, 7),
        payg_total=Decimal("60.00"),
        optimized_total=Decimal("47.50"),
        selections=(travelcard_selection(),))
    assert result.savings == Decimal("12.50")


def test_optimization_result_savings_can_be_negative() -> None:
    """Verify that optimization result savings can be negative."""
    result = OptimizationResult(
        journey_start_date=date(2026, 3, 1),
        journey_end_date=date(2026, 3, 1),
        payg_total=Decimal("5.60"),
        optimized_total=Decimal("6.00"),
        selections=(payg_selection(),))
    assert result.savings == Decimal("-0.40")


def test_optimization_result_uses_travelcard_detects_selection() -> None:
    """Verify that optimization result uses travelcard detects selection."""
    result = OptimizationResult(
        journey_start_date=date(2026, 3, 1),
        journey_end_date=date(2026, 3, 7),
        payg_total=Decimal("60.00"),
        optimized_total=Decimal("47.50"),
        selections=(payg_selection(), travelcard_selection()))
    assert result.uses_travelcard


def test_optimization_result_uses_travelcard_is_false_for_payg_only() -> None:
    """Verify that optimization result uses travelcard is false for PAYG only."""
    result = OptimizationResult(
        journey_start_date=date(2026, 3, 1),
        journey_end_date=date(2026, 3, 1),
        payg_total=Decimal("5.60"),
        optimized_total=Decimal("5.60"),
        selections=(payg_selection(),))
    assert not result.uses_travelcard
