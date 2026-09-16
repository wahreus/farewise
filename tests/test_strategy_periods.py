from datetime import date, time
from decimal import Decimal

from src.journeys import Journey
from src.optimizer import _build_strategy_periods
from src.payg import group_journeys_by_date
from src.results import (
    BusTramPassSelection,
    PaygSelection,
    StrategyPeriodSelection,
    TravelcardSelection,
)


def make_journey(day: date, amount: str = "2.00") -> Journey:
    return Journey(
        date=day,
        start_time=time(8, 0),
        end_time=time(8, 30),
        start_station="A",
        end_station="B",
        start_network="underground",
        end_network="underground",
        charged_amount=Decimal(amount),
    )


def assert_periods_do_not_overlap(
    periods: tuple[StrategyPeriodSelection, ...],
) -> None:
    for previous, current in zip(periods, periods[1:]):
        assert previous.end_date < current.start_date


def test_bus_pass_absorbs_residual_payg_inside_its_period() -> None:
    start = date(2026, 7, 17)
    journeys = [
        make_journey(date(2026, 7, day))
        for day in range(17, 25)
    ]
    selections = (
        BusTramPassSelection(
            product_name="7 Day Bus & Tram Pass",
            start_date=start,
            end_date=date(2026, 7, 23),
            pass_cost=Decimal("24.70"),
            covered_journey_count=1,
        ),
        *(
            PaygSelection(
                start_date=date(2026, 7, day),
                end_date=date(2026, 7, day),
                cost=Decimal("2.00"),
                journey_count=1,
            )
            for day in range(18, 25)
        ),
    )

    periods = _build_strategy_periods(
        selections,
        group_journeys_by_date(journeys),
        start,
        date(2026, 7, 24),
    )

    assert all(isinstance(period, StrategyPeriodSelection) for period in periods)
    assert len(periods) == 2

    pass_period = periods[0]
    assert pass_period.start_date == date(2026, 7, 17)
    assert pass_period.end_date == date(2026, 7, 23)
    assert pass_period.bus_tram_pass_product_name == "7 Day Bus & Tram Pass"
    assert pass_period.bus_tram_pass_cost == Decimal("24.70")
    assert pass_period.payg_cost == Decimal("12.00")
    assert pass_period.payg_journey_count == 6
    assert pass_period.total_cost == Decimal("36.70")

    payg_period = periods[1]
    assert payg_period.start_date == date(2026, 7, 24)
    assert payg_period.end_date == date(2026, 7, 24)
    assert payg_period.bus_tram_pass_product_name is None
    assert payg_period.payg_cost == Decimal("2.00")
    assert payg_period.payg_journey_count == 1

    assert_periods_do_not_overlap(periods)


def test_travelcard_period_can_include_residual_payg() -> None:
    start = date(2026, 7, 25)
    journeys = []
    for day in range(25, 32):
        journeys.extend(
            [
                make_journey(date(2026, 7, day)),
                make_journey(date(2026, 7, day)),
            ]
        )
    journeys.extend(
        [
            make_journey(date(2026, 7, 29), "3.30"),
            make_journey(date(2026, 7, 29), "3.30"),
        ]
    )

    selections = (
        TravelcardSelection(
            product_name="7 Day",
            zone_name="Zones 1-3",
            max_zone=3,
            start_date=start,
            end_date=date(2026, 7, 31),
            card_cost=Decimal("52.50"),
            outside_payg_cost=Decimal("0.00"),
            covered_journey_count=14,
            uncovered_journey_count=2,
        ),
        PaygSelection(
            start_date=date(2026, 7, 29),
            end_date=date(2026, 7, 29),
            cost=Decimal("6.60"),
            journey_count=2,
        ),
    )

    periods = _build_strategy_periods(
        selections,
        group_journeys_by_date(journeys),
        start,
        date(2026, 7, 31),
    )

    assert len(periods) == 1
    period = periods[0]
    assert isinstance(period, StrategyPeriodSelection)
    assert period.start_date == date(2026, 7, 25)
    assert period.end_date == date(2026, 7, 31)
    assert period.travelcard_product_name == "7 Day"
    assert period.travelcard_zone_name == "Zones 1-3"
    assert period.travelcard_cost == Decimal("52.50")
    assert period.covered_journey_count == 14
    assert period.payg_cost == Decimal("6.60")
    assert period.payg_journey_count == 2
    assert period.total_cost == Decimal("59.10")

    assert_periods_do_not_overlap(periods)
