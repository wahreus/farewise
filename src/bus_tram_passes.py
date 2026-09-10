"""Bus & Tram Pass option construction and journey coverage."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from src.fares import BusAndTramPassPrices, FareData
from src.journeys import BUS_MODE, Journey
from src.periods import DatePeriod, PeriodKind, build_period
from src.results import BusTramPassSelection


class BusTramPassType(str, Enum):
    """Bus & Tram Pass products considered by the optimizer."""

    ONE_DAY = "1 Day Bus & Tram Pass"
    SEVEN_DAY = "7 Day Bus & Tram Pass"
    MONTHLY = "Monthly Bus & Tram Pass"


@dataclass(frozen=True)
class BusTramPassOption:
    """One Bus & Tram Pass product, period and price."""

    product: BusTramPassType
    period: DatePeriod
    price: Decimal


def period_kind(product: BusTramPassType) -> PeriodKind:
    """Map a Bus & Tram Pass product to its validity period kind."""

    if product == BusTramPassType.ONE_DAY:
        return PeriodKind.ONE_DAY
    if product == BusTramPassType.SEVEN_DAY:
        return PeriodKind.SEVEN_DAY
    return PeriodKind.MONTHLY


def product_price(
    prices: BusAndTramPassPrices,
    product: BusTramPassType,
) -> Decimal:
    """Return the configured price for a Bus & Tram Pass product."""

    if product == BusTramPassType.ONE_DAY:
        return prices.one_day
    if product == BusTramPassType.SEVEN_DAY:
        return prices.seven_day
    return prices.monthly


def build_bus_tram_pass_options(
    start_date: date,
    fare_data: FareData,
) -> list[BusTramPassOption]:
    """Build all Bus & Tram Pass options starting on a given date."""

    prices = fare_data.bus_and_tram_pass
    if prices is None:
        return []

    return [
        BusTramPassOption(
            product=product,
            period=build_period(start_date, period_kind(product)),
            price=product_price(prices, product),
        )
        for product in BusTramPassType
    ]


def option_covers_journey(
    option: BusTramPassOption,
    journey: Journey,
) -> bool:
    """Return whether a Bus & Tram Pass option covers a supported journey."""

    # FareWise currently parses bus journeys but not tram journeys.
    # Add TRAM_MODE here when tram journey parsing is implemented.
    return option.period.contains(journey.date) and journey.mode == BUS_MODE


def create_bus_tram_pass_selection(
    option: BusTramPassOption,
    journeys: list[Journey],
) -> BusTramPassSelection:
    """Build the result entry for one purchased Bus & Tram Pass."""

    covered_count = sum(
        option_covers_journey(option, journey)
        for journey in journeys
    )
    return BusTramPassSelection(
        product_name=option.product.value,
        start_date=option.period.start_date,
        end_date=option.period.end_date,
        pass_cost=option.price,
        covered_journey_count=covered_count,
    )
