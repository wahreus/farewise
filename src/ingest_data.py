from pathlib import Path
import csv
import re

FIELDNAMES = ["date",
              "start_time",
              "end_time",
              "start_station",
              "end_station",
              "start_network",
              "end_network",
              "charged_amount"]


NETWORK_FILES = {"underground": "london_underground_stations.csv",
                 "dlr": "london_dlr_stations.csv",
                 "overground": "london_overground_stations.csv"}

def find_repo_root() -> Path:
    start = Path(__file__).resolve().parent
    for folder in [start, *start.parents]:
        has_raw = (folder / "data" / "raw" / "journey_history.csv").exists()
        has_refs = (folder / "data" / "reference").exists()
        if has_raw and has_refs:
            return folder
    raise FileNotFoundError("Could not find data/raw/journey_history.csv and data/reference/. "
                            "Put this script in farewise/src/ and run it from inside the repo.")

def clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())

def key(value: object) -> str:
    return clean_text(value).casefold()

def read_station_names(path: Path) -> dict[str, str]:
    stations: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            station = clean_text(row.get("Station", ""))
            if station:
                stations[key(station)] = station
    return stations

def read_reference_data(reference_dir: Path) -> dict[str, dict[str, str]]:
    return {network: read_station_names(reference_dir / filename)
            for network, filename in NETWORK_FILES.items()}

def split_action(action: str) -> tuple[str, str] | None:
    parts = re.split(r"\s+to\s+", clean_text(action), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]

def remove_marker(endpoint: str) -> tuple[str, str] | None:
    """
    Convert raw TfL endpoint text into station text + network.

    Examples:
      Oxford Circus                         -> Oxford Circus, underground
      Limehouse DLR                         -> Limehouse, dlr
      Surrey Quays [London Overground]      -> Surrey Quays, overground
      [No touch-out]                        -> [No touch-out], unknown
    """
    text = clean_text(endpoint)
    lower = text.casefold()
    if lower in {"[no touch-out]", "[no touch-in]"}:
        return text, "unknown"
    bracket_match = re.search(r"\s+\[([^\]]+)\]$", text)
    if bracket_match:
        label = bracket_match.group(1).casefold()
        station = text[: bracket_match.start()].strip()
        if label == "london underground":
            return station, "underground"
        if label == "london overground":
            return station, "overground"
        if label == "dlr":
            return station, "dlr"
        return None
    if lower.endswith(" dlr"):
        return text[:-4].strip(), "dlr"
    return text, "underground"

def parse_endpoint(endpoint: str,
                   stations: dict[str, dict[str, str]],
                   ) -> tuple[str, str] | None:
    parsed = remove_marker(endpoint)
    if parsed is None:
        return None
    station, network = parsed
    if network == "unknown":
        return station, network
    official_name = stations[network].get(key(station))
    if official_name is None:
        return None
    return official_name, network

def clean_charge(value: object) -> str | None:
    text = clean_text(value).replace("£", "").replace(",", "")
    if not text:
        return None
    try:
        return str(float(text))
    except ValueError:
        return None

def clean_row(row: dict[str, str],
              stations: dict[str, dict[str, str]],
              ) -> dict[str, str] | None:
    action = split_action(row.get("Journey/Action", ""))
    if action is None:
        return None
    start = parse_endpoint(action[0], stations)
    end = parse_endpoint(action[1], stations)
    charge = clean_charge(row.get("Charge", ""))
    if start is None or end is None or charge is None:
        return None
    start_station, start_network = start
    end_station, end_network = end
    return {"date": clean_text(row.get("Date", "")),
            "start_time": clean_text(row.get("Start Time", "")),
            "end_time": clean_text(row.get("End Time", "")),
            "start_station": start_station,
            "end_station": end_station,
            "start_network": start_network,
            "end_network": end_network,
            "charged_amount": charge}

def main() -> None:
    root = find_repo_root()
    input_path = root / "data" / "raw" / "journey_history.csv"
    reference_dir = root / "data" / "reference"
    output_path = root / "data" / "processed" / "journey_history_processed.csv"
    stations = read_reference_data(reference_dir)
    cleaned_rows: list[dict[str, str]] = []
    with input_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            cleaned = clean_row(row, stations)
            if cleaned is not None:
                cleaned_rows.append(cleaned)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(cleaned_rows)

if __name__ == "__main__":
    main()
