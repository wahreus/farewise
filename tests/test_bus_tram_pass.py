"""Tests for Bus & Tram Pass optimization and overlapping pass products."""

from datetime import date, time, timedelta
from decimal import Decimal

from src.fares import (
    BusAndTramPassPrices,
    FareData,
    PayAsYouGoCaps,
    TravelcardPrices,
    UndergroundFareOption,
)
from src.journeys import BUS_MODE, Journey
from src.optimizer import optimize_fares
from src.results import BusTramPassSelection, TravelcardSelection
from src.stations import Station


def fare_data() -> FareData:
    """Build fares that make an overlapping pass combination optimal."""

    return FareData(
        valid_from="2026-03-01",
        currency="GBP",
        underground={
            "zone_1": UndergroundFareOption(
                pay_as_you_go=PayAsYouGoCaps(
                    daily_anytime_cap=Decimal("100.00"),
                    daily_off_peak_cap=Decimal("100.00"),
                    weekly_cap=Decimal("100.00"),
                ),
                travelcard=TravelcardPrices(
                    one_day_anytime=Decimal("100.00"),
                    one_day_off_peak=Decimal("100.00"),
                    seven_day=Decimal("10.00"),
                    monthly=Decimal("100.00"),
                ),
            )
        },
        bus_and_tram_pass=BusAndTramPassPrices(
            one_day=Decimal("100.00"),
            seven_day=Decimal("100.00"),
            monthly=Decimal("20.00"),
        ),
    )


def bus_journey(day: date) -> Journey:
    """Build one bus journey."""

    return Journey(
        date=day,
        start_time=time(8, 0),
        end_time=None,
        start_station="",
        end_station="",
        start_network="",
        end_network="",
        charged_amount=Decimal("2.00"),
        mode=BUS_MODE,
        route="1",
    )


def rail_journey(day: date) -> Journey:
    """Build one Zone 1 rail journey."""

    return Journey(
        date=day,
        start_time=time(10, 0),
        end_time=time(10, 30),
        start_station="A",
        end_station="B",
        start_network="underground",
        end_network="underground",
        charged_amount=Decimal("8.00"),
    )


def test_optimizer_combines_overlapping_bus_pass_and_travelcard() -> None:
    """A Bus & Tram Pass may stay active while a Travelcard starts."""

    first_day = date(2026, 4, 1)

    journeys = [
        bus_journey(first_day + timedelta(days=offset))
        for offset in range(60)
    ]
    journeys.extend(
        rail_journey(first_day + timedelta(days=offset))
        for offset in range(24, 31)
    )

    stations = {
        ("underground", "a"): Station("A", ["Test"], ["1"]),
        ("underground", "b"): Station("B", ["Test"], ["1"]),
    }

    result = optimize_fares(journeys, stations, fare_data())

    bus_passes = [
        selection
        for selection in result.selections
        if isinstance(selection, BusTramPassSelection)
    ]
    travelcards = [
        selection
        for selection in result.selections
        if isinstance(selection, TravelcardSelection)
    ]

    assert result.optimized_total == Decimal("50.00")
    assert bus_passes
    assert travelcards

    assert any(
        bus_pass.start_date <= travelcard.end_date
        and travelcard.start_date <= bus_pass.end_date
        for bus_pass in bus_passes
        for travelcard in travelcards
    )


def test_bus_pass_does_not_cover_rail() -> None:
    """Rail remains PAYG unless a Travelcard covers it."""

    first_day = date(2026, 4, 1)
    journeys = [
        bus_journey(first_day),
        rail_journey(first_day),
    ]

    stations = {
        ("underground", "a"): Station("A", ["Test"], ["1"]),
        ("underground", "b"): Station("B", ["Test"], ["1"]),
    }

    fares = fare_data()
    fares = FareData(
        valid_from=fares.valid_from,
        currency=fares.currency,
        underground={
            "zone_1": UndergroundFareOption(
                pay_as_you_go=fares.underground["zone_1"].pay_as_you_go,
                travelcard=TravelcardPrices(
                    one_day_anytime=Decimal("100.00"),
                    one_day_off_peak=Decimal("100.00"),
                    seven_day=Decimal("100.00"),
                    monthly=Decimal("100.00"),
                ),
            )
        },
        bus_and_tram_pass=BusAndTramPassPrices(
            one_day=Decimal("1.00"),
            seven_day=Decimal("100.00"),
            monthly=Decimal("100.00"),
        ),
    )

    result = optimize_fares(journeys, stations, fares)

    assert result.optimized_total == Decimal("9.00")
    assert result.uses_bus_tram_pass
    assert not result.uses_travelcard
