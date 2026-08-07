"""Fare optimization logic for comparing PAYG and Travelcard strategies."""

from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Iterable
from src.fares import FareData
from src.journeys import Journey
from src.payg import (calculate_payg_total,
                      create_payg_selection,
                      group_journeys_by_date)
from src.results import (OptimizationResult,
                         PaymentSelection,
                         PaygSelection,
                         TravelcardSelection)
from src.stations import Station
from src.travelcards import build_travelcard_options, evaluate_travelcard

ZERO = Decimal("0.00")

def selection_key(total_cost: Decimal,
                  selections: tuple[PaymentSelection, ...],
                  ) -> tuple[Decimal, int, int]:
    """Build the ordering key used to compare fare strategies."""
    travelcard_count = sum(isinstance(selection, TravelcardSelection)
                           for selection in selections)
    return total_cost, travelcard_count, len(selections)

def merge_adjacent_payg(selections: tuple[PaymentSelection, ...],
                        ) -> tuple[PaymentSelection, ...]:
    """Merge consecutive PAYG selections into continuous periods."""
    merged: list[PaymentSelection] = []
    for selection in selections:
        if (isinstance(selection, PaygSelection)
                and merged
                and isinstance(merged[-1], PaygSelection)
                and merged[-1].end_date + timedelta(days=1)
                == selection.start_date):
            previous = merged[-1]
            merged[-1] = PaygSelection(
                start_date=previous.start_date,
                end_date=selection.end_date,
                cost=previous.cost + selection.cost,
                journey_count=previous.journey_count + selection.journey_count)
        else:
            merged.append(selection)
    return tuple(merged)

def build_warnings(journeys: list[Journey],
                   fare_data: FareData,
                   ) -> tuple[str, ...]:
    """Build limitation warnings for an optimization result."""
    warnings = [
        "Travelcard coverage is estimated from journey endpoints; routes "
        "and boundary extension fares are not modelled.",
        "Journeys outside Travelcard coverage keep their recorded PAYG "
        "charge; PAYG caps are not recalculated.",
        "One Day Off-Peak uses a simplified rule: weekends or journeys "
        "starting at or after 09:30 on weekdays."]
    try:
        valid_from = date.fromisoformat(fare_data.valid_from)
    except ValueError:
        valid_from = None
    if valid_from is not None and any(journey.date < valid_from
                                      for journey in journeys):
        warnings.insert(
            0,
            "The journey history predates the fare table, so the comparison "
            f"mixes recorded charges with fares valid from {fare_data.valid_from}.")
    return tuple(warnings)

def optimize_fares(journeys: Iterable[Journey],
                   stations: dict[tuple[str, str], Station],
                   fare_data: FareData,
                   ) -> OptimizationResult:
    """Find the lowest-cost combination of PAYG and Travelcards."""
    journey_list = sorted(journeys, key=lambda journey: journey.starts_at)
    if not journey_list:
        raise ValueError("At least one journey is required")
    history_start = journey_list[0].date
    history_end = journey_list[-1].date
    history_day_count = (history_end - history_start).days + 1
    journeys_by_date = group_journeys_by_date(journey_list)

    @lru_cache(maxsize=None)
    def solve(day_index: int) -> tuple[Decimal, tuple[PaymentSelection, ...]]:
        """Return the cheapest strategy from the given history day onward."""
        if day_index >= history_day_count:
            return ZERO, ()
        current_date = history_start + timedelta(days=day_index)
        daily_journeys = journeys_by_date.get(current_date, [])
        future_cost, future_selections = solve(day_index + 1)
        daily_cost = calculate_payg_total(daily_journeys)
        if daily_journeys:
            payg_selections: tuple[PaymentSelection, ...] = (
                create_payg_selection(current_date, daily_journeys),
                *future_selections)
        else:
            payg_selections = future_selections
        best_cost = daily_cost + future_cost
        best_selections = payg_selections

        if daily_journeys:
            for option in build_travelcard_options(current_date, fare_data):
                period_journeys = [
                    journey for journey in journey_list
                    if option.period.contains(journey.date)]
                selection = evaluate_travelcard(option,
                                                period_journeys,
                                                stations)
                next_date = option.period.end_date + timedelta(days=1)
                next_index = min((next_date - history_start).days,
                                 history_day_count)
                remaining_cost, remaining_selections = solve(next_index)
                candidate_cost = selection.total_cost + remaining_cost
                candidate_selections: tuple[PaymentSelection, ...] = (
                    selection,
                    *remaining_selections)
                if (selection_key(candidate_cost, candidate_selections)
                        < selection_key(best_cost, best_selections)):
                    best_cost = candidate_cost
                    best_selections = candidate_selections
        return best_cost, best_selections

    optimized_total, selections = solve(0)
    return OptimizationResult(
        journey_start_date=history_start,
        journey_end_date=history_end,
        payg_total=calculate_payg_total(journey_list),
        optimized_total=optimized_total,
        selections=merge_adjacent_payg(selections),
        warnings=build_warnings(journey_list, fare_data))
