"""Fare optimization across PAYG, Travelcards and Bus & Tram Passes."""

from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Iterable

from src.bus_tram_passes import (
    BusTramPassOption,
    build_bus_tram_pass_options,
    create_bus_tram_pass_selection,
    option_covers_journey as bus_tram_pass_covers_journey,
)
from src.fares import FareData
from src.journeys import Journey
from src.payg import (
    calculate_payg_total,
    create_payg_selection,
    group_journeys_by_date,
)
from src.results import (
    BusTramPassSelection,
    OptimizationResult,
    PaymentSelection,
    PaygSelection,
    TravelcardSelection,
)
from src.stations import Station
from src.travelcards import (
    TravelcardOption,
    build_travelcard_options,
    evaluate_travelcard,
    option_covers_journey as travelcard_covers_journey,
)

ZERO = Decimal("0.00")


def selection_key(
    total_cost: Decimal,
    selections: tuple[PaymentSelection, ...],
) -> tuple[Decimal, int, int]:
    """Build the ordering key used to compare fare strategies."""

    pass_count = sum(
        isinstance(selection, (TravelcardSelection, BusTramPassSelection))
        for selection in selections
    )
    return total_cost, pass_count, len(selections)


def merge_adjacent_payg(
    selections: tuple[PaymentSelection, ...],
) -> tuple[PaymentSelection, ...]:
    """Merge consecutive PAYG selections into continuous periods."""

    merged: list[PaymentSelection] = []
    for selection in selections:
        if (
            isinstance(selection, PaygSelection)
            and merged
            and isinstance(merged[-1], PaygSelection)
            and merged[-1].end_date + timedelta(days=1) == selection.start_date
        ):
            previous = merged[-1]
            merged[-1] = PaygSelection(
                start_date=previous.start_date,
                end_date=selection.end_date,
                cost=previous.cost + selection.cost,
                journey_count=previous.journey_count + selection.journey_count,
            )
        else:
            merged.append(selection)
    return tuple(merged)


def build_warnings(
    journeys: list[Journey],
    fare_data: FareData,
) -> tuple[str, ...]:
    """Build limitation warnings for an optimization result."""

    if fare_data.bus_and_tram_pass is None:
        warnings = [
            "Travelcard coverage is estimated from journey endpoints; routes "
            "and boundary extension fares are not modelled.",
            "Journeys outside Travelcard coverage keep their recorded PAYG "
            "charge; PAYG caps are not recalculated.",
            "One Day Off-Peak uses a simplified rule: weekends or journeys "
            "starting at or after 09:30 on weekdays.",
        ]
    else:
        warnings = [
            "Travelcard coverage is estimated from journey endpoints; routes "
            "and boundary extension fares are not modelled.",
            "Journeys not covered by any active pass keep their recorded PAYG "
            "charge; PAYG caps are not recalculated.",
            "One Day Off-Peak uses a simplified rule: weekends or journeys "
            "starting at or after 09:30 on weekdays.",
            "Bus & Tram Pass coverage currently applies to supported bus "
            "journeys; tram journey parsing is not yet implemented.",
        ]

    try:
        valid_from = date.fromisoformat(fare_data.valid_from)
    except ValueError:
        valid_from = None

    if valid_from is not None and any(
        journey.date < valid_from for journey in journeys
    ):
        warnings.insert(
            0,
            "The journey history predates the fare table, so the comparison "
            f"mixes recorded charges with fares valid from {fare_data.valid_from}.",
        )

    return tuple(warnings)


def _optimize_travelcard_only(
    journeys: Iterable[Journey],
    stations: dict[tuple[str, str], Station],
    fare_data: FareData,
) -> OptimizationResult:
    """Run the original Travelcard/PAYG optimizer unchanged."""

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
                *future_selections,
            )
        else:
            payg_selections = future_selections
        best_cost = daily_cost + future_cost
        best_selections = payg_selections

        if daily_journeys:
            for option in build_travelcard_options(current_date, fare_data):
                period_journeys = [
                    journey
                    for journey in journey_list
                    if option.period.contains(journey.date)
                ]
                selection = evaluate_travelcard(
                    option,
                    period_journeys,
                    stations,
                )
                next_date = option.period.end_date + timedelta(days=1)
                next_index = min(
                    (next_date - history_start).days,
                    history_day_count,
                )
                remaining_cost, remaining_selections = solve(next_index)
                candidate_cost = selection.total_cost + remaining_cost
                candidate_selections: tuple[PaymentSelection, ...] = (
                    selection,
                    *remaining_selections,
                )

                if (
                    selection_key(candidate_cost, candidate_selections)
                    < selection_key(best_cost, best_selections)
                ):
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
        warnings=build_warnings(journey_list, fare_data),
    )


def _optimize_with_bus_tram_passes(
    journeys: Iterable[Journey],
    stations: dict[tuple[str, str], Station],
    fare_data: FareData,
) -> OptimizationResult:
    """Optimize with one independently active pass from each product family."""

    journey_list = sorted(journeys, key=lambda journey: journey.starts_at)
    if not journey_list:
        raise ValueError("At least one journey is required")

    history_start = journey_list[0].date
    history_end = journey_list[-1].date
    history_day_count = (history_end - history_start).days + 1
    journeys_by_date = group_journeys_by_date(journey_list)

    @lru_cache(maxsize=None)
    def travelcard_purchase_selection(
        option: TravelcardOption,
    ) -> TravelcardSelection:
        """Build a Travelcard purchase result without attaching PAYG to it."""

        period_journeys = [
            journey
            for journey in journey_list
            if option.period.contains(journey.date)
        ]
        covered_count = sum(
            travelcard_covers_journey(option, journey, stations)
            for journey in period_journeys
        )
        return TravelcardSelection(
            product_name=option.product.value,
            zone_name=option.zone_name,
            max_zone=option.max_zone,
            start_date=option.period.start_date,
            end_date=option.period.end_date,
            card_cost=option.price,
            outside_payg_cost=ZERO,
            covered_journey_count=covered_count,
            uncovered_journey_count=len(period_journeys) - covered_count,
        )

    @lru_cache(maxsize=None)
    def bus_tram_purchase_selection(
        option: BusTramPassOption,
    ) -> BusTramPassSelection:
        """Build a Bus & Tram Pass purchase result."""

        period_journeys = [
            journey
            for journey in journey_list
            if option.period.contains(journey.date)
        ]
        return create_bus_tram_pass_selection(option, period_journeys)

    def covered_by_active_passes(
        journey: Journey,
        travelcard: TravelcardOption | None,
        bus_tram_pass: BusTramPassOption | None,
    ) -> bool:
        """Return whether either active pass covers a journey."""

        if (
            travelcard is not None
            and travelcard_covers_journey(travelcard, journey, stations)
        ):
            return True

        return (
            bus_tram_pass is not None
            and bus_tram_pass_covers_journey(bus_tram_pass, journey)
        )

    def travelcard_start_options(
        current_date: date,
        daily_journeys: list[Journey],
        active_travelcard: TravelcardOption | None,
    ) -> tuple[TravelcardOption | None, ...]:
        """Return worthwhile Travelcards that may start today."""

        if active_travelcard is not None or not daily_journeys:
            return (None,)

        options = [
            option
            for option in build_travelcard_options(current_date, fare_data)
            if any(
                travelcard_covers_journey(option, journey, stations)
                for journey in daily_journeys
            )
        ]
        return (None, *options)

    def bus_tram_start_options(
        current_date: date,
        daily_journeys: list[Journey],
        active_bus_tram_pass: BusTramPassOption | None,
    ) -> tuple[BusTramPassOption | None, ...]:
        """Return worthwhile Bus & Tram Passes that may start today."""

        if active_bus_tram_pass is not None or not daily_journeys:
            return (None,)

        options = [
            option
            for option in build_bus_tram_pass_options(current_date, fare_data)
            if any(
                bus_tram_pass_covers_journey(option, journey)
                for journey in daily_journeys
            )
        ]
        return (None, *options)

    @lru_cache(maxsize=None)
    def solve(
        day_index: int,
        active_travelcard: TravelcardOption | None,
        active_bus_tram_pass: BusTramPassOption | None,
    ) -> tuple[Decimal, tuple[PaymentSelection, ...]]:
        """Return the cheapest strategy from one day and active-pass state."""

        if day_index >= history_day_count:
            return ZERO, ()

        current_date = history_start + timedelta(days=day_index)

        if (
            active_travelcard is not None
            and active_travelcard.period.end_date < current_date
        ):
            active_travelcard = None

        if (
            active_bus_tram_pass is not None
            and active_bus_tram_pass.period.end_date < current_date
        ):
            active_bus_tram_pass = None

        daily_journeys = journeys_by_date.get(current_date, [])

        travelcard_starts = travelcard_start_options(
            current_date,
            daily_journeys,
            active_travelcard,
        )
        bus_tram_starts = bus_tram_start_options(
            current_date,
            daily_journeys,
            active_bus_tram_pass,
        )

        best_cost: Decimal | None = None
        best_selections: tuple[PaymentSelection, ...] = ()

        for new_travelcard in travelcard_starts:
            effective_travelcard = active_travelcard or new_travelcard

            for new_bus_tram_pass in bus_tram_starts:
                effective_bus_tram_pass = (
                    active_bus_tram_pass or new_bus_tram_pass
                )

                today_cost = ZERO
                today_selections: list[PaymentSelection] = []

                if new_travelcard is not None:
                    today_cost += new_travelcard.price
                    today_selections.append(
                        travelcard_purchase_selection(new_travelcard)
                    )

                if new_bus_tram_pass is not None:
                    today_cost += new_bus_tram_pass.price
                    today_selections.append(
                        bus_tram_purchase_selection(new_bus_tram_pass)
                    )

                uncovered_journeys = [
                    journey
                    for journey in daily_journeys
                    if not covered_by_active_passes(
                        journey,
                        effective_travelcard,
                        effective_bus_tram_pass,
                    )
                ]

                if uncovered_journeys:
                    payg_selection = create_payg_selection(
                        current_date,
                        uncovered_journeys,
                    )
                    today_cost += payg_selection.total_cost
                    today_selections.append(payg_selection)

                next_travelcard = (
                    effective_travelcard
                    if (
                        effective_travelcard is not None
                        and effective_travelcard.period.end_date > current_date
                    )
                    else None
                )
                next_bus_tram_pass = (
                    effective_bus_tram_pass
                    if (
                        effective_bus_tram_pass is not None
                        and effective_bus_tram_pass.period.end_date > current_date
                    )
                    else None
                )

                future_cost, future_selections = solve(
                    day_index + 1,
                    next_travelcard,
                    next_bus_tram_pass,
                )
                candidate_cost = today_cost + future_cost
                candidate_selections = (
                    *today_selections,
                    *future_selections,
                )

                if (
                    best_cost is None
                    or selection_key(candidate_cost, candidate_selections)
                    < selection_key(best_cost, best_selections)
                ):
                    best_cost = candidate_cost
                    best_selections = candidate_selections

        if best_cost is None:
            raise RuntimeError("Optimizer did not produce a candidate strategy")

        return best_cost, best_selections

    optimized_total, selections = solve(0, None, None)

    return OptimizationResult(
        journey_start_date=history_start,
        journey_end_date=history_end,
        payg_total=calculate_payg_total(journey_list),
        optimized_total=optimized_total,
        selections=merge_adjacent_payg(selections),
        warnings=build_warnings(journey_list, fare_data),
    )


def optimize_fares(
    journeys: Iterable[Journey],
    stations: dict[tuple[str, str], Station],
    fare_data: FareData,
) -> OptimizationResult:
    """Find the lowest-cost FareWise payment strategy."""

    if fare_data.bus_and_tram_pass is None:
        return _optimize_travelcard_only(journeys, stations, fare_data)

    return _optimize_with_bus_tram_passes(journeys, stations, fare_data)
