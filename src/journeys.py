import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from src.stations import NETWORK_FILES

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
DATE_FORMATS = ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
TIME_FORMATS = ("%H:%M", "%H:%M:%S")
RAW_FIELDS = {"Date", "Start Time", "End Time", "Journey/Action", "Charge"}

class JourneyParseError(ValueError):
    pass

@dataclass(frozen=True)
class Journey:
    date: date
    start_time: time
    end_time: time | None
    start_station: str
    end_station: str
    start_network: str
    end_network: str
    charged_amount: Decimal
    @property
    def starts_at(self) -> datetime:
        return datetime.combine(self.date, self.start_time)

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
    parts = re.split(r"\s+to\s+", clean_text(action), maxsplit=1,
                     flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]

def remove_marker(endpoint: str) -> tuple[str, str] | None:
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

def parse_date(value: str) -> date:
    text = value.strip()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise JourneyParseError(f"Unsupported journey date: {value!r}")

def parse_time(value: str) -> time:
    text = value.strip()
    for time_format in TIME_FORMATS:
        try:
            return datetime.strptime(text, time_format).time()
        except ValueError:
            continue
    raise JourneyParseError(f"Unsupported journey time: {value!r}")

def parse_optional_time(value: str) -> time | None:
    if not value.strip():
        return None
    return parse_time(value)

def parse_amount(value: str) -> Decimal:
    text = value.strip().replace("£", "").replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise JourneyParseError(f"Unsupported journey charge: {value!r}") from error

def journey_from_row(row: dict[str, str],
                     row_number: int | None = None,
                     ) -> Journey:
    try:
        start_station = row["start_station"].strip()
        end_station = row["end_station"].strip()
        start_network = row["start_network"].strip().casefold()
        end_network = row["end_network"].strip().casefold()
        if not start_station or not end_station:
            raise JourneyParseError("Station names cannot be empty")
        if not start_network or not end_network:
            raise JourneyParseError("Network names cannot be empty")
        return Journey(
            date=parse_date(row["date"]),
            start_time=parse_time(row["start_time"]),
            end_time=parse_optional_time(row["end_time"]),
            start_station=start_station,
            end_station=end_station,
            start_network=start_network,
            end_network=end_network,
            charged_amount=parse_amount(row["charged_amount"]))
    except (KeyError, JourneyParseError) as error:
        location = f" at CSV row {row_number}" if row_number is not None else ""
        raise JourneyParseError(f"Invalid journey{location}: {error}") from error

def load_raw_journeys(reader: csv.DictReader,
                      reference_dir: str | Path,
                      ) -> list[Journey]:
    stations = read_reference_data(Path(reference_dir))
    journeys = []
    for row_number, row in enumerate(reader, start=2):
        cleaned = clean_row(row, stations)
        if cleaned is not None:
            journeys.append(journey_from_row(cleaned, row_number))
    return journeys

def load_journeys(csv_path: str | Path,
                  reference_dir: str | Path = REFERENCE_DIR,
                  ) -> list[Journey]:
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fields = set(reader.fieldnames or [])
        if not RAW_FIELDS.issubset(fields):
            raise JourneyParseError("CSV does not match the raw TfL format")
        journeys = load_raw_journeys(reader, reference_dir)
    if not journeys:
        raise JourneyParseError("No supported journeys were found in the CSV")
    return sorted(journeys, key=lambda journey: journey.starts_at)
