"""Tests for station-zone lookup and journey coverage logic."""

from datetime import date, time
from decimal import Decimal
from pathlib import Path

from src import coverage
from src.journeys import Journey
from src.stations import Station


def sample_stations() -> dict[tuple[str, str], Station]:
    """Return representative station data for coverage tests."""
    return {
        coverage.station_key("underground", "Oxford Circus"): Station(
            name="Oxford Circus",
            lines=["Central", "Victoria"],
            zones=["1"]),
        coverage.station_key("underground", "Earl's Court"): Station(
            name="Earl's Court",
            lines=["District", "Piccadilly"],
            zones=["1", "2"]),
        coverage.station_key("dlr", "Stratford"): Station(
            name="Stratford",
            lines=["DLR"],
            zones=["2/3"]),
        coverage.station_key("overground", "Watford Junction"): Station(
            name="Watford Junction",
            lines=["Lioness"],
            zones=["Special"])}


def make_journey(start_station: str = "Oxford Circus",
                 end_station: str = "Earl's Court",
                 start_network: str = "underground",
                 end_network: str = "underground",
                 ) -> Journey:
    """Build a representative journey with configurable endpoints."""
    return Journey(date=date(2026, 3, 1),
                   start_time=time(8, 10),
                   end_time=time(8, 25),
                   start_station=start_station,
                   end_station=end_station,
                   start_network=start_network,
                   end_network=end_network,
                   charged_amount=Decimal("2.80"))


def write_station_file(path: Path,
                       station_name: str,
                       zones: str,
                       ) -> None:
    """Write a minimal station reference CSV file."""
    path.write_text(
        "Station,Line(s),Zone(s)\n"
        f"{station_name},Example,{zones}\n",
        encoding="utf-8")


def test_station_key_normalizes_network_and_station_name() -> None:
    """Verify that station key normalizes network and station name."""
    assert coverage.station_key(" UNDERGROUND ", " Oxford Circus ") == (
        "underground",
        "oxford circus")


def test_load_station_lookup_loads_all_network_files(tmp_path) -> None:
    """Verify that load station lookup loads all network files."""
    write_station_file(tmp_path / "london_underground_stations.csv",
                       "Oxford Circus",
                       "1")
    write_station_file(tmp_path / "london_dlr_stations.csv",
                       "Limehouse",
                       "2")
    write_station_file(tmp_path / "london_overground_stations.csv",
                       "Surrey Quays",
                       "2")
    stations = coverage.load_station_lookup(tmp_path)
    assert set(stations) == {
        ("underground", "oxford circus"),
        ("dlr", "limehouse"),
        ("overground", "surrey quays")}
    assert stations[("dlr", "limehouse")].name == "Limehouse"


def test_station_zones_returns_all_numeric_zones() -> None:
    """Verify that station zones returns all numeric zones."""
    assert coverage.station_zones("Stratford",
                                  "dlr",
                                  sample_stations()) == {2, 3}


def test_station_zones_normalizes_lookup_values() -> None:
    """Verify that station zones normalizes lookup values."""
    assert coverage.station_zones("  OXFORD CIRCUS ",
                                  " UNDERGROUND ",
                                  sample_stations()) == {1}


def test_station_zones_returns_none_for_unknown_station() -> None:
    """Verify that station zones returns none for unknown station."""
    assert coverage.station_zones("Unknown",
                                  "underground",
                                  sample_stations()) is None


def test_station_zones_returns_none_without_numeric_zone() -> None:
    """Verify that station zones returns none without numeric zone."""
    assert coverage.station_zones("Watford Junction",
                                  "overground",
                                  sample_stations()) is None


def test_station_is_covered_accepts_boundary_station_zone() -> None:
    """Verify that station is covered accepts boundary station zone."""
    assert coverage.station_is_covered("Stratford",
                                       "dlr",
                                       2,
                                       sample_stations())


def test_station_is_covered_rejects_station_outside_max_zone() -> None:
    """Verify that station is covered rejects station outside max zone."""
    assert not coverage.station_is_covered("Stratford",
                                           "dlr",
                                           1,
                                           sample_stations())


def test_station_is_covered_rejects_unknown_station() -> None:
    """Verify that station is covered rejects unknown station."""
    assert not coverage.station_is_covered("Unknown",
                                           "underground",
                                           2,
                                           sample_stations())


def test_journey_is_covered_requires_both_endpoints() -> None:
    """Verify that journey is covered requires both endpoints."""
    stations = sample_stations()
    assert coverage.journey_is_covered(make_journey(), 1, stations)
    assert not coverage.journey_is_covered(
        make_journey(end_station="Stratford", end_network="dlr"),
        1,
        stations)


def test_minimum_journey_max_zone_uses_lowest_zone_for_each_station() -> None:
    """Verify that minimum journey max zone uses lowest zone for each station."""
    journey = make_journey(end_station="Stratford", end_network="dlr")
    assert coverage.minimum_journey_max_zone(
        journey,
        sample_stations()) == 2


def test_minimum_journey_max_zone_returns_none_for_unknown_endpoint() -> None:
    """Verify that minimum journey max zone returns none for unknown endpoint."""
    journey = make_journey(end_station="Unknown")
    assert coverage.minimum_journey_max_zone(
        journey,
        sample_stations()) is None
