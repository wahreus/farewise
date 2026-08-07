"""Tests for Travelcard options, eligibility, coverage, and pricing."""

from datetime import date, time
from decimal import Decimal

import pytest

from src.fares import (FareData,
                       PayAsYouGoCaps,
                       TravelcardPrices,
                       UndergroundFareOption)
from src.journeys import Journey
from src.periods import DatePeriod, PeriodKind
from src.results import TravelcardSelection
from src.stations import Station
from src.travelcards import (TravelcardOption,
                             TravelcardType,
                             build_travelcard_options,
                             display_zone_name,
                             evaluate_travelcard,
                             max_zone_from_name,
                             off_peak_eligible,
                             option_covers_journey,
                             period_kind,
                             product_price)


def fare_option() -> UndergroundFareOption:
    """Return representative PAYG caps and Travelcard prices."""
    return UndergroundFareOption(
        pay_as_you_go=PayAsYouGoCaps(
            daily_anytime_cap=Decimal("8.90"),
            daily_off_peak_cap=Decimal("8.90"),
            weekly_cap=Decimal("44.70")),
        travelcard=TravelcardPrices(
            one_day_anytime=Decimal("16.60"),
            one_day_off_peak=Decimal("16.60"),
            seven_day=Decimal("44.70"),
            monthly=Decimal("171.70")))


def sample_fare_data() -> FareData:
    """Return fare data for two representative zone ranges."""
    return FareData(valid_from="2026-03-01",
                    currency="GBP",
                    underground={"zones_1_2": fare_option(),
                                 "zones_1_4": fare_option()})


def sample_stations() -> dict[tuple[str, str], Station]:
    """Return representative stations spanning several zones."""
    return {("underground", "oxford circus"): Station(
                name="Oxford Circus",
                lines=["Central", "Victoria"],
                zones=["1"]),
            ("underground", "stratford"): Station(
                name="Stratford",
                lines=["Central"],
                zones=["2", "3"]),
            ("underground", "epping"): Station(
                name="Epping",
                lines=["Central"],
                zones=["6"])}


def make_journey(journey_date: date = date(2026, 3, 2),
                 start_time: time = time(10, 0),
                 start_station: str = "Oxford Circus",
                 end_station: str = "Stratford",
                 charged_amount: str = "2.80",
                 ) -> Journey:
    """Build a configurable journey for Travelcard tests."""
    return Journey(date=journey_date,
                   start_time=start_time,
                   end_time=time(10, 20),
                   start_station=start_station,
                   end_station=end_station,
                   start_network="underground",
                   end_network="underground",
                   charged_amount=Decimal(charged_amount))


def make_option(product: TravelcardType = TravelcardType.SEVEN_DAY,
                max_zone: int = 2,
                start_date: date = date(2026, 3, 1),
                end_date: date = date(2026, 3, 7),
                price: str = "44.70",
                ) -> TravelcardOption:
    """Build a configurable Travelcard option for coverage tests."""
    return TravelcardOption(
        product=product,
        zone_name="Zones 1-2",
        max_zone=max_zone,
        period=DatePeriod(kind=period_kind(product),
                          start_date=start_date,
                          end_date=end_date),
        price=Decimal(price))


@pytest.mark.parametrize(
    ("zone_name", "expected"),
    [("zones_1_2", 2),
     ("Zones 1-6", 6),
     ("Zone 1", 1)])
def test_max_zone_from_name_returns_last_zone_number(
    zone_name: str,
    expected: int,
    ) -> None:
    """Verify that max zone from name returns last zone number."""
    assert max_zone_from_name(zone_name) == expected


def test_max_zone_from_name_rejects_name_without_number() -> None:
    """Verify that max zone from name rejects name without number."""
    with pytest.raises(ValueError, match="Invalid fare zone name"):
        max_zone_from_name("all zones")


@pytest.mark.parametrize(
    ("zone_name", "expected"),
    [("zones_1_1", "Zone 1"),
     ("zones_1_2", "Zones 1-2"),
     ("zones_1_6", "Zones 1-6")])
def test_display_zone_name_formats_zone_range(
    zone_name: str,
    expected: str,
    ) -> None:
    """Verify that display zone name formats zone range."""
    assert display_zone_name(zone_name) == expected


@pytest.mark.parametrize(
    ("product", "expected"),
    [(TravelcardType.ONE_DAY_ANYTIME, PeriodKind.ONE_DAY),
     (TravelcardType.ONE_DAY_OFF_PEAK, PeriodKind.ONE_DAY),
     (TravelcardType.SEVEN_DAY, PeriodKind.SEVEN_DAY),
     (TravelcardType.MONTHLY, PeriodKind.MONTHLY)])
def test_period_kind_maps_travelcard_product(
    product: TravelcardType,
    expected: PeriodKind,
    ) -> None:
    """Verify that period kind maps travelcard product."""
    assert period_kind(product) == expected


@pytest.mark.parametrize(
    ("product", "expected"),
    [(TravelcardType.ONE_DAY_ANYTIME, Decimal("16.60")),
     (TravelcardType.ONE_DAY_OFF_PEAK, Decimal("16.60")),
     (TravelcardType.SEVEN_DAY, Decimal("44.70")),
     (TravelcardType.MONTHLY, Decimal("171.70"))])
def test_product_price_returns_matching_travelcard_price(
    product: TravelcardType,
    expected: Decimal,
    ) -> None:
    """Verify that product price returns matching travelcard price."""
    assert product_price(fare_option(), product) == expected


def test_build_travelcard_options_builds_every_product_and_zone() -> None:
    """Verify that build travelcard options builds every product and zone."""
    options = build_travelcard_options(date(2026, 3, 1), sample_fare_data())
    assert len(options) == 8
    assert options[0] == TravelcardOption(
        product=TravelcardType.ONE_DAY_ANYTIME,
        zone_name="Zones 1-2",
        max_zone=2,
        period=DatePeriod(kind=PeriodKind.ONE_DAY,
                          start_date=date(2026, 3, 1),
                          end_date=date(2026, 3, 1)),
        price=Decimal("16.60"))
    assert options[-1].product == TravelcardType.MONTHLY
    assert options[-1].zone_name == "Zones 1-4"
    assert options[-1].period.end_date == date(2026, 3, 31)


@pytest.mark.parametrize(
    ("journey_date", "start_time", "expected"),
    [(date(2026, 3, 2), time(9, 29), False),
     (date(2026, 3, 2), time(9, 30), True),
     (date(2026, 3, 7), time(8, 0), True),
     (date(2026, 3, 8), time(8, 0), True)])
def test_off_peak_eligible_uses_weekday_time_and_weekends(
    journey_date: date,
    start_time: time,
    expected: bool,
    ) -> None:
    """Verify off-peak eligibility for weekday times and weekends."""
    assert off_peak_eligible(
        make_journey(journey_date=journey_date,
                     start_time=start_time)) is expected


def test_option_covers_journey_inside_period_time_and_zones() -> None:
    """Verify that option covers journey inside period time and zones."""
    assert option_covers_journey(make_option(),
                                 make_journey(),
                                 sample_stations())


def test_option_covers_journey_rejects_date_outside_period() -> None:
    """Verify that option covers journey rejects date outside period."""
    assert not option_covers_journey(
        make_option(),
        make_journey(journey_date=date(2026, 3, 8)),
        sample_stations())


def test_option_covers_journey_rejects_peak_off_peak_journey() -> None:
    """Verify that option covers journey rejects peak off peak journey."""
    option = make_option(product=TravelcardType.ONE_DAY_OFF_PEAK,
                         start_date=date(2026, 3, 2),
                         end_date=date(2026, 3, 2))
    assert not option_covers_journey(
        option,
        make_journey(start_time=time(8, 0)),
        sample_stations())


def test_option_covers_journey_rejects_station_outside_zones() -> None:
    """Verify that option covers journey rejects station outside zones."""
    assert not option_covers_journey(
        make_option(),
        make_journey(end_station="Epping"),
        sample_stations())


def test_evaluate_travelcard_counts_covered_and_uncovered_journeys() -> None:
    """Verify that evaluate travelcard counts covered and uncovered journeys."""
    option = make_option(price="44.70")
    journeys = [make_journey(charged_amount="2.80"),
                make_journey(end_station="Epping", charged_amount="3.60"),
                make_journey(journey_date=date(2026, 3, 8),
                             charged_amount="4.00")]
    selection = evaluate_travelcard(option, journeys, sample_stations())
    assert selection == TravelcardSelection(
        product_name="7 Day",
        zone_name="Zones 1-2",
        max_zone=2,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 7),
        card_cost=Decimal("44.70"),
        outside_payg_cost=Decimal("7.60"),
        covered_journey_count=1,
        uncovered_journey_count=2)
