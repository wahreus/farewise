"""Tests for PAYG grouping, totals, and selection creation."""

from datetime import date, time
from decimal import Decimal

from src.journeys import Journey
from src.payg import (calculate_payg_total,
                      create_payg_selection,
                      group_journeys_by_date)
from src.results import PaygSelection


def make_journey(journey_date: date,
                 charged_amount: str,
                 ) -> Journey:
    """Build a journey with the supplied date and recorded charge."""
    return Journey(date=journey_date,
                   start_time=time(8, 10),
                   end_time=time(8, 25),
                   start_station="Oxford Circus",
                   end_station="Bank",
                   start_network="underground",
                   end_network="underground",
                   charged_amount=Decimal(charged_amount))


def test_group_journeys_by_date_groups_matching_dates() -> None:
    """Verify that group journeys by date groups matching dates."""
    first_date = date(2026, 3, 1)
    second_date = date(2026, 3, 2)
    journeys = [make_journey(first_date, "2.80"),
                make_journey(second_date, "3.00"),
                make_journey(first_date, "2.90")]
    grouped = group_journeys_by_date(journeys)
    assert list(grouped) == [first_date, second_date]
    assert grouped[first_date] == [journeys[0], journeys[2]]
    assert grouped[second_date] == [journeys[1]]


def test_group_journeys_by_date_accepts_empty_iterable() -> None:
    """Verify that group journeys by date accepts empty iterable."""
    assert group_journeys_by_date([]) == {}


def test_calculate_payg_total_sums_recorded_charges() -> None:
    """Verify that calculate PAYG total sums recorded charges."""
    journeys = [make_journey(date(2026, 3, 1), "2.80"),
                make_journey(date(2026, 3, 1), "3.10")]
    assert calculate_payg_total(journeys) == Decimal("5.90")


def test_calculate_payg_total_returns_decimal_zero_for_no_journeys() -> None:
    """Verify that calculate PAYG total returns decimal zero for no journeys."""
    assert calculate_payg_total([]) == Decimal("0.00")


def test_create_payg_selection_builds_expected_selection() -> None:
    """Verify that create PAYG selection builds expected selection."""
    selection_date = date(2026, 3, 1)
    journeys = [make_journey(selection_date, "2.80"),
                make_journey(selection_date, "3.10")]
    selection = create_payg_selection(selection_date, journeys)
    assert selection == PaygSelection(start_date=selection_date,
                                      end_date=selection_date,
                                      cost=Decimal("5.90"),
                                      journey_count=2)


def test_create_payg_selection_consumes_iterable_once() -> None:
    """Verify that create PAYG selection consumes iterable once."""
    selection_date = date(2026, 3, 1)
    journeys = (make_journey(selection_date, charge)
                for charge in ["2.80", "3.10"])
    selection = create_payg_selection(selection_date, journeys)
    assert selection.cost == Decimal("5.90")
    assert selection.journey_count == 2
