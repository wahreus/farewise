import csv
from dataclasses import dataclass
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"
STATIONS_CSV = DATA_DIR / "london_underground_stations.csv"


@dataclass
class Station:
    name: str
    lines: list[str]
    zones: list[str]


def load_station_data(csv_path: str | Path) -> dict[str, Station]:
    stations = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            station = Station(
                name=row["Station"].strip(),
                lines=[line.strip() for line in row["Line(s)"].split("|")],
                zones=[zone.strip() for zone in row["Zone(s)"].split("|")]
            )
            stations[station.name.lower()] = station
    return stations


def main():
    stations = load_station_data(STATIONS_CSV)
    print(f"Loaded {len(stations)} stations")
    station = stations["earl's court"]
    print("Example:", station)


if __name__ == "__main__":
    main()