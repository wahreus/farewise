import json
from decimal import Decimal

from src.fares import (FareData,
                       UndergroundFareOption,
                       as_decimal,
                       format_money,
                       load_fare_data)

def test_as_decimal_converts_supported_values() -> None:
    assert as_decimal("12.30") == Decimal("12.30")
    assert as_decimal(12) == Decimal("12")
    assert as_decimal(12.5) == Decimal("12.5")
    assert as_decimal(Decimal("12.30")) == Decimal("12.30")

def test_load_fare_data_builds_expected_objects(tmp_path) -> None:
    fare_path = tmp_path / "fares.json"
    fare_path.write_text(
        json.dumps(
            {"valid_from": "2026-03-01",
                "currency": "GBP",
                "underground": {
                    "zones_1_2": {
                        "pay_as_you_go": {
                            "daily_anytime_cap": "8.90",
                            "daily_off_peak_cap": "8.90",
                            "weekly_cap": "44.70"},
                        "travelcard": {
                            "one_day_anytime": "16.60",
                            "one_day_off_peak": "16.60",
                            "seven_day": "44.70",
                            "monthly": "171.70"}}}}),
                        encoding="utf-8",)
    fare_data = load_fare_data(fare_path)
    assert isinstance(fare_data, FareData)
    assert fare_data.valid_from == "2026-03-01"
    assert fare_data.currency == "GBP"
    option = fare_data.underground["zones_1_2"]
    assert isinstance(option, UndergroundFareOption)
    assert option.pay_as_you_go.daily_anytime_cap == Decimal("8.90")
    assert option.pay_as_you_go.daily_off_peak_cap == Decimal("8.90")
    assert option.pay_as_you_go.weekly_cap == Decimal("44.70")
    assert option.travelcard.one_day_anytime == Decimal("16.60")
    assert option.travelcard.one_day_off_peak == Decimal("16.60")
    assert option.travelcard.seven_day == Decimal("44.70")
    assert option.travelcard.monthly == Decimal("171.70")

def test_format_money_uses_pounds_and_two_decimal_places() -> None:
    assert format_money(Decimal("5")) == "£5.00"
    assert format_money(Decimal("12.3")) == "£12.30"
    assert format_money(Decimal("0.009")) == "£0.01"
