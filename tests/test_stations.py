"""Tests for loading and normalizing station reference data."""

from src.stations import Station, load_station_data

def test_load_station_data_parses_station_lines_and_zones(tmp_path) -> None:
    """Verify that load station data parses station lines and zones."""
    station_path = tmp_path / "stations.csv"
    station_path.write_text("Station,Line(s),Zone(s)\n"
                            "Earl's Court,District | Piccadilly,1 | 2\n"
                            "Oxford Circus,Bakerloo | Central | Victoria,1\n",
                            encoding="utf-8-sig")
    stations = load_station_data(station_path)
    assert set(stations) == {"earl's court", "oxford circus"}
    assert stations["earl's court"] == Station(name="Earl's Court",
                                               lines=["District", "Piccadilly"],
                                               zones=["1", "2"])
    assert stations["oxford circus"] == Station(
        name="Oxford Circus",
        lines=["Bakerloo", "Central", "Victoria"],
        zones=["1"])

def test_load_station_data_strips_station_name(tmp_path) -> None:
    """Verify that load station data strips station name."""
    station_path = tmp_path / "stations.csv"
    station_path.write_text(
        "Station,Line(s),Zone(s)\n"
        "  Bank  ,Central | Northern,1\n",
        encoding="utf-8")
    stations = load_station_data(station_path)
    assert list(stations) == ["bank"]
    assert stations["bank"].name == "Bank"
