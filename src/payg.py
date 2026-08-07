"""PAYG grouping and cost helpers for FareWise."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Iterable
from src.journeys import Journey
from src.results import PaygSelection

ZERO = Decimal("0.00")

def group_journeys_by_date(journeys: Iterable[Journey],
                           ) -> dict[date, list[Journey]]:
    """Group journeys by their travel date."""
    grouped = defaultdict(list)
    for journey in journeys:
        grouped[journey.date].append(journey)
    return dict(grouped)

def calculate_payg_total(journeys: Iterable[Journey]) -> Decimal:
    """Sum the recorded PAYG charges for the given journeys."""
    return sum((journey.charged_amount for journey in journeys), start=ZERO)

def create_payg_selection(selection_date: date,
                          journeys: Iterable[Journey],
                          ) -> PaygSelection:
    """Build a PAYG selection for one date and its journeys."""
    daily_journeys = tuple(journeys)
    return PaygSelection(start_date=selection_date,
                         end_date=selection_date,
                         cost=calculate_payg_total(daily_journeys),
                         journey_count=len(daily_journeys))
