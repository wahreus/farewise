from datetime import date, time
from decimal import Decimal

import pytest

from src.fares import (FareData,
                       PayAsYouGoCaps,
                       TravelcardPrices,
                       UndergroundFareOption)
from src.journeys import Journey
from src.optimizer import (build_warnings,
                           merge_adjacent_payg,
                           optimize_fares,
                           selection_key)
from src.results import PaygSelection, TravelcardSelection
from src.stations import Station


def make_journey(journey_date: date,
                 charged_amount: str = "4.00",
                 end_station: str = "Bank",
                 ) -> Journey:
    return Journey(date=journey_date,
                   start_time=time(8, 10),
                   end_time=time(8, 25),
                   start_station="Oxford Circus",
                   end_station=end_station,
                   start_network="underground",
                   end_network="underground",
                   charged_amount=Decimal(charged_amount))


def make_fare_data(one_day_anytime: str = "20.00",
                   one_day_off_peak: str = "20.00",
                   seven_day: str = "20.00",
                   monthly: str = "100.00",
                   valid_from: str = "2026-03-01",
                   ) -> FareData:
    option = UndergroundFareOption(
        pay_as_you_go=PayAsYouGoCaps(
            daily_anytime_cap=Decimal("8.90"),
            daily_off_peak_cap=Decimal("8.90"),
            weekly_cap=Decimal("44.70")),
        travelcard=TravelcardPrices(
            one_day_anytime=Decimal(one_day_anytime),
            one_day_off_peak=Decimal(one_day_off_peak),
            seven_day=Decimal(seven_day),
            monthly=Decimal(monthly)))
    return FareData(valid_from=valid_from,
                    currency="GBP",
                    underground={"zones_1_2": option})


def sample_stations() -> dict[tuple[str, str], Station]:
    return {("underground", "oxford circus"): Station(
                name="Oxford Circus",
                lines=["Central", "Victoria"],
                zones=["1"]),
            ("underground", "bank"): Station(
                name="Bank",
                lines=["Central", "Northern"],
                zones=["1"]),
            ("underground", "epping"): Station(
                name="Epping",
                lines=["Central"],
                zones=["6"])}


def payg_selection(start_date: date,
                   end_date: date,
                   cost: str,
                   journey_count: int,
                   ) -> PaygSelection:
    return PaygSelection(start_date=start_date,
                         end_date=end_date,
                         cost=Decimal(cost),
                         journey_count=journey_count)


def travelcard_selection() -> TravelcardSelection:
    return TravelcardSelection(product_name="7 Day",
                               zone_name="Zones 1–2",
                               max_zone=2,
                               start_date=date(2026, 3, 1),
                               end_date=date(2026, 3, 7),
                               card_cost=Decimal("44.70"),
                               outside_payg_cost=Decimal("0.00"),
                               covered_journey_count=2,
                               uncovered_journey_count=0)


def test_selection_key_counts_travelcards_and_selections() -> None:
    selections = (payg_selection(date(2026, 3, 1),
                                 date(2026, 3, 1),
                                 "4.00",
                                 1),
                  travelcard_selection())
    assert selection_key(Decimal("48.70"), selections) == (
        Decimal("48.70"),
        1,
        2)


def test_merge_adjacent_payg_combines_consecutive_selections() -> None:
    selections = (
        payg_selection(date(2026, 3, 1), date(2026, 3, 1), "4.00", 1),
        payg_selection(date(2026, 3, 2), date(2026, 3, 2), "5.00", 2),
        payg_selection(date(2026, 3, 4), date(2026, 3, 4), "3.00", 1))
    assert merge_adjacent_payg(selections) == (
        payg_selection(date(2026, 3, 1), date(2026, 3, 2), "9.00", 3),
        payg_selection(date(2026, 3, 4), date(2026, 3, 4), "3.00", 1))


def test_merge_adjacent_payg_does_not_merge_across_travelcard() -> None:
    first = payg_selection(date(2026, 3, 1),
                           date(2026, 3, 1),
                           "4.00",
                           1)
    second = payg_selection(date(2026, 3, 2),
                            date(2026, 3, 2),
                            "5.00",
                            1)
    selections = (first, travelcard_selection(), second)
    assert merge_adjacent_payg(selections) == selections


def test_build_warnings_returns_standard_limitations() -> None:
    warnings = build_warnings([make_journey(date(2026, 3, 1))],
                              make_fare_data())
    assert len(warnings) == 3
    assert warnings[0].startswith("Travelcard coverage is estimated")
    assert warnings[1].startswith("Journeys outside Travelcard coverage")
    assert warnings[2].startswith("One Day Off-Peak")


def test_build_warnings_adds_warning_for_older_journeys() -> None:
    warnings = build_warnings([make_journey(date(2026, 2, 28))],
                              make_fare_data())
    assert len(warnings) == 4
    assert warnings[0] == (
        "The journey history predates the fare table, so the comparison "
        "mixes recorded charges with fares valid from 2026-03-01.")


def test_build_warnings_ignores_invalid_valid_from_date() -> None:
    warnings = build_warnings([make_journey(date(2026, 2, 28))],
                              make_fare_data(valid_from="unknown"))
    assert len(warnings) == 3


def test_optimize_fares_rejects_empty_journey_history() -> None:
    with pytest.raises(ValueError, match="At least one journey is required"):
        optimize_fares([], sample_stations(), make_fare_data())


def test_optimize_fares_uses_payg_when_travelcards_cost_more() -> None:
    journeys = [make_journey(date(2026, 3, 2), "4.00"),
                make_journey(date(2026, 3, 1), "4.00")]
    result = optimize_fares(journeys,
                            sample_stations(),
                            make_fare_data())
    assert result.journey_start_date == date(2026, 3, 1)
    assert result.journey_end_date == date(2026, 3, 2)
    assert result.payg_total == Decimal("8.00")
    assert result.optimized_total == Decimal("8.00")
    assert result.selections == (
        payg_selection(date(2026, 3, 1),
                       date(2026, 3, 2),
                       "8.00",
                       2),)
    assert not result.uses_travelcard


def test_optimize_fares_keeps_separate_payg_periods_across_empty_day() -> None:
    journeys = [make_journey(date(2026, 3, 1), "4.00"),
                make_journey(date(2026, 3, 3), "5.00")]
    result = optimize_fares(journeys,
                            sample_stations(),
                            make_fare_data())
    assert result.selections == (
        payg_selection(date(2026, 3, 1),
                       date(2026, 3, 1),
                       "4.00",
                       1),
        payg_selection(date(2026, 3, 3),
                       date(2026, 3, 3),
                       "5.00",
                       1))


def test_optimize_fares_chooses_cheaper_seven_day_travelcard() -> None:
    journeys = [make_journey(date(2026, 3, 1), "4.00"),
                make_journey(date(2026, 3, 2), "4.00")]
    result = optimize_fares(
        journeys,
        sample_stations(),
        make_fare_data(seven_day="5.00"))
    assert result.payg_total == Decimal("8.00")
    assert result.optimized_total == Decimal("5.00")
    assert len(result.selections) == 1
    selection = result.selections[0]
    assert isinstance(selection, TravelcardSelection)
    assert selection.product_name == "7 Day"
    assert selection.start_date == date(2026, 3, 1)
    assert selection.end_date == date(2026, 3, 7)
    assert selection.covered_journey_count == 2
    assert selection.uncovered_journey_count == 0


def test_optimize_fares_prefers_payg_when_cost_is_tied() -> None:
    journey = make_journey(date(2026, 3, 1), "4.00")
    result = optimize_fares(
        [journey],
        sample_stations(),
        make_fare_data(one_day_anytime="4.00",
                       one_day_off_peak="4.00",
                       seven_day="4.00",
                       monthly="4.00"))
    assert result.optimized_total == Decimal("4.00")
    assert result.selections == (
        payg_selection(date(2026, 3, 1),
                       date(2026, 3, 1),
                       "4.00",
                       1),)


def test_optimize_fares_keeps_outside_journey_as_recorded_payg() -> None:
    journeys = [make_journey(date(2026, 3, 1), "4.00"),
                make_journey(date(2026, 3, 2),
                             "6.00",
                             end_station="Epping")]
    result = optimize_fares(
        journeys,
        sample_stations(),
        make_fare_data(seven_day="3.00"))
    assert result.optimized_total == Decimal("9.00")
    selection = result.selections[0]
    assert isinstance(selection, TravelcardSelection)
    assert selection.card_cost == Decimal("3.00")
    assert selection.outside_payg_cost == Decimal("6.00")
    assert selection.covered_journey_count == 1
    assert selection.uncovered_journey_count == 1
