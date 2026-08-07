"""Station reference models and CSV loading utilities."""

import csv
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
FARES_JSON = DATA_DIR / "reference" / "fares_2026.json"
STATIONS_CSV = DATA_DIR / "reference" / "london_underground_stations.csv"
NETWORK_FILES = {"underground": "london_underground_stations.csv",
                 "dlr": "london_dlr_stations.csv",
                 "overground": "london_overground_stations.csv"}

@dataclass
class Station:
    """Station name, served lines and fare zones."""
    name: str
    lines: list[str]
    zones: list[str]

def load_station_data(csv_path: str | Path) -> dict[str, Station]:
    """Load station records from a reference CSV file."""
    stations = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            station = Station(
                name=row["Station"].strip(),
                lines=[line.strip() for line in row["Line(s)"].split("|")],
                zones=[zone.strip() for zone in row["Zone(s)"].split("|")])
            stations[station.name.lower()] = station
    return stations

def main():
    """Load station data and print a small inspection summary."""
    stations = load_station_data(STATIONS_CSV)
    print(f"Loaded {len(stations)} stations")
    station = stations["earl's court"]
    print("Example:", station)

if __name__ == "__main__":
    main()
