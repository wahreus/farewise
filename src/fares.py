"""Fare data models and loading utilities for FareWise."""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
FARES_JSON = DATA_DIR / "reference" / "fares_2026.json"
STATIONS_CSV = DATA_DIR / "reference" / "london_underground_stations.csv"

@dataclass(frozen=True)
class PayAsYouGoCaps:
    """PAYG cap values for one fare-zone option."""
    daily_anytime_cap: Decimal
    daily_off_peak_cap: Decimal
    weekly_cap: Decimal

@dataclass(frozen=True)
class TravelcardPrices:
    """Travelcard prices for one fare-zone option."""
    one_day_anytime: Decimal
    one_day_off_peak: Decimal
    seven_day: Decimal
    monthly: Decimal

@dataclass(frozen=True)
class UndergroundFareOption:
    """PAYG and Travelcard fares for one zone range."""
    pay_as_you_go: PayAsYouGoCaps
    travelcard: TravelcardPrices

@dataclass(frozen=True)
class FareData:
    """Complete FareWise fare table and metadata."""
    valid_from: str
    currency: str
    underground: dict[str, UndergroundFareOption]

def as_decimal(value: str | int | float | Decimal) -> Decimal:
    """Convert a supported numeric value to Decimal."""
    return Decimal(str(value))

def load_fare_data(json_path: str | Path) -> FareData:
    """Load fare data from the configured JSON structure."""
    with open(json_path, encoding="utf-8") as file:
        data = json.load(file)
    underground = {}
    for zone_name, values in data["underground"].items():
        payg = values["pay_as_you_go"]
        travelcard = values["travelcard"]
        underground[zone_name] = UndergroundFareOption(
            pay_as_you_go=PayAsYouGoCaps(
                daily_anytime_cap=as_decimal(payg["daily_anytime_cap"]),
                daily_off_peak_cap=as_decimal(payg["daily_off_peak_cap"]),
                weekly_cap=as_decimal(payg["weekly_cap"])),
            travelcard=TravelcardPrices(
                one_day_anytime=as_decimal(travelcard["one_day_anytime"]),
                one_day_off_peak=as_decimal(travelcard["one_day_off_peak"]),
                seven_day=as_decimal(travelcard["seven_day"]),
                monthly=as_decimal(travelcard["monthly"])))
    return FareData(valid_from=data["valid_from"],
                    currency=data["currency"],
                    underground=underground)

def format_money(value: Decimal) -> str:
    """Format a Decimal value as pounds and pence."""
    return f"£{value:.2f}"

def main() -> None:
    """Print the configured fare table for inspection."""
    fare_data = load_fare_data(FARES_JSON)
    print(f"\nFares valid from: {fare_data.valid_from}")
    print(f"Currency: {fare_data.currency}\n")
    for zone_name, option in fare_data.underground.items():
        print(zone_name)
        print("  Pay as you go caps")
        print(f"    Daily anytime: {format_money(option.pay_as_you_go.daily_anytime_cap)}")
        print(f"    Daily off-peak: {format_money(option.pay_as_you_go.daily_off_peak_cap)}")
        print(f"    Weekly: {format_money(option.pay_as_you_go.weekly_cap)}")
        print("  Travelcards")
        print(f"    One day anytime: {format_money(option.travelcard.one_day_anytime)}")
        print(f"    One day off-peak: {format_money(option.travelcard.one_day_off_peak)}")
        print(f"    7 day: {format_money(option.travelcard.seven_day)}")
        print(f"    Monthly: {format_money(option.travelcard.monthly)}\n")

if __name__ == "__main__":
    main()
