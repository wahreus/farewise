import re
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from enum import Enum
from typing import Iterable
from src.coverage import journey_is_covered
from src.fares import FareData, UndergroundFareOption
from src.journeys import Journey
from src.periods import DatePeriod, PeriodKind, build_period
from src.results import TravelcardSelection
from src.stations import Station

OFF_PEAK_START = time(9, 30)
ZERO = Decimal("0.00")

class TravelcardType(str, Enum):
    ONE_DAY_ANYTIME = "1 Day Anytime"
    ONE_DAY_OFF_PEAK = "1 Day Off-Peak"
    SEVEN_DAY = "7 Day"
    MONTHLY = "Monthly"

@dataclass(frozen=True)
class TravelcardOption:
    product: TravelcardType
    zone_name: str
    max_zone: int
    period: DatePeriod
    price: Decimal

def max_zone_from_name(zone_name: str) -> int:
    numbers = re.findall(r"\d+", zone_name)
    if not numbers:
        raise ValueError(f"Invalid fare zone name: {zone_name!r}")
    return int(numbers[-1])

def display_zone_name(zone_name: str) -> str:
    max_zone = max_zone_from_name(zone_name)
    if max_zone == 1:
        return "Zone 1"
    return f"Zones 1-{max_zone}"

def period_kind(product: TravelcardType) -> PeriodKind:
    if product in {TravelcardType.ONE_DAY_ANYTIME,
                   TravelcardType.ONE_DAY_OFF_PEAK}:
        return PeriodKind.ONE_DAY
    if product == TravelcardType.SEVEN_DAY:
        return PeriodKind.SEVEN_DAY
    return PeriodKind.MONTHLY

def product_price(option: UndergroundFareOption,
                  product: TravelcardType,
                  ) -> Decimal:
    prices = option.travelcard
    if product == TravelcardType.ONE_DAY_ANYTIME:
        return prices.one_day_anytime
    if product == TravelcardType.ONE_DAY_OFF_PEAK:
        return prices.one_day_off_peak
    if product == TravelcardType.SEVEN_DAY:
        return prices.seven_day
    return prices.monthly

def build_travelcard_options(start_date: date,
                             fare_data: FareData,
                             ) -> list[TravelcardOption]:
    options = []
    for zone_name, fare_option in fare_data.underground.items():
        max_zone = max_zone_from_name(zone_name)
        for product in TravelcardType:
            options.append(
                TravelcardOption(
                    product=product,
                    zone_name=display_zone_name(zone_name),
                    max_zone=max_zone,
                    period=build_period(start_date, period_kind(product)),
                    price=product_price(fare_option, product)))
    return options

def off_peak_eligible(journey: Journey) -> bool:
    return journey.date.weekday() >= 5 or journey.start_time >= OFF_PEAK_START

def option_covers_journey(option: TravelcardOption,
                          journey: Journey,
                          stations: dict[tuple[str, str], Station],
                          ) -> bool:
    if not option.period.contains(journey.date):
        return False
    if (option.product == TravelcardType.ONE_DAY_OFF_PEAK
            and not off_peak_eligible(journey)):
        return False
    return journey_is_covered(journey, option.max_zone, stations)

def evaluate_travelcard(option: TravelcardOption,
                        journeys: Iterable[Journey],
                        stations: dict[tuple[str, str], Station],
                        ) -> TravelcardSelection:
    covered_count = 0
    uncovered_count = 0
    outside_payg_cost = ZERO
    for journey in journeys:
        if option_covers_journey(option, journey, stations):
            covered_count += 1
        else:
            uncovered_count += 1
            outside_payg_cost += journey.charged_amount
    return TravelcardSelection(
        product_name=option.product.value,
        zone_name=option.zone_name,
        max_zone=option.max_zone,
        start_date=option.period.start_date,
        end_date=option.period.end_date,
        card_cost=option.price,
        outside_payg_cost=outside_payg_cost,
        covered_journey_count=covered_count,
        uncovered_journey_count=uncovered_count)
