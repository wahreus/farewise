import re
from pathlib import Path
from src.ingest_data import NETWORK_FILES
from src.journeys import Journey
from src.stations import Station, load_station_data

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"

def station_key(network: str, station_name: str) -> tuple[str, str]:
    return network.strip().casefold(), station_name.strip().casefold()

def load_station_lookup(reference_dir: str | Path = REFERENCE_DIR,
                        ) -> dict[tuple[str, str], Station]:
    reference_path = Path(reference_dir)
    stations = {}
    for network, filename in NETWORK_FILES.items():
        network_stations = load_station_data(reference_path / filename)
        for station in network_stations.values():
            stations[station_key(network, station.name)] = station
    return stations

def station_zones(station_name: str,
                  network: str,
                  stations: dict[tuple[str, str], Station],
                  ) -> set[int] | None:
    station = stations.get(station_key(network, station_name))
    if station is None:
        return None
    zones = set()
    for zone in station.zones:
        zones.update(int(number) for number in re.findall(r"\d+", zone))
    return zones or None

def station_is_covered(station_name: str,
                       network: str,
                       max_zone: int,
                       stations: dict[tuple[str, str], Station],
                       ) -> bool:
    zones = station_zones(station_name, network, stations)
    if zones is None:
        return False
    return any(zone <= max_zone for zone in zones)

def journey_is_covered(journey: Journey,
                       max_zone: int,
                       stations: dict[tuple[str, str], Station],
                       ) -> bool:
    return (station_is_covered(journey.start_station,
                               journey.start_network,
                               max_zone,
                               stations)
            and station_is_covered(journey.end_station,
                                   journey.end_network,
                                   max_zone,
                                   stations))

def minimum_journey_max_zone(journey: Journey,
                             stations: dict[tuple[str, str], Station],
                             ) -> int | None:
    start_zones = station_zones(journey.start_station,
                                journey.start_network,
                                stations)
    end_zones = station_zones(journey.end_station,
                              journey.end_network,
                              stations)
    if start_zones is None or end_zones is None:
        return None
    return max(min(start_zones), min(end_zones))
