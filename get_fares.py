import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"
FARES_JSON = DATA_DIR / "fares_2026.json"


@dataclass
class FareData:
    valid_from: str
    currency: str
    underground: dict[str, UndergroundFareOption]


@dataclass
class UndergroundFareOption:
    daily_cap: Decimal
    weekly_cap: Decimal
    monthly_travelcard: Decimal


def load_fare_data(json_path: str | Path) -> FareData:
    with open(json_path, encoding="utf-8") as file:
        data = json.load(file)
    underground = {}
    for zone_name, values in data["underground"].items():
        underground[zone_name] = UndergroundFareOption(
            daily_cap=Decimal(values["daily_cap"]),
            weekly_cap=Decimal(values["weekly_cap"]),
            monthly_travelcard=Decimal(values["monthly_travelcard"]),
        )

    return FareData(
               valid_from=data["valid_from"],
               currency=data["currency"],
               underground=underground,
           )


def main():
    fare_data = load_fare_data(FARES_JSON)
    print(f"\nFares valid from: {fare_data.valid_from}")
    print(f"Currency: {fare_data.currency}\n")
    for zone_name, option in fare_data.underground.items():
        print(zone_name)
        print(f"  Daily cap: £{option.daily_cap}")
        print(f"  Weekly cap: £{option.weekly_cap}")
        print(f"  Monthly Travelcard: £{option.monthly_travelcard}\n")


if __name__ == "__main__":
    main()