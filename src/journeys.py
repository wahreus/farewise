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
UNSUPPORTED_TRANSPORT_MODE = "unsupported_transport_mode"
NON_JOURNEY_ACTION = "non_journey_action"
UNKNOWN_STATION = "unknown_station"
INVALID_CHARGE = "invalid_charge"

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

@dataclass(frozen=True)
class JourneyLoadSummary:
    loaded_count: int
    unsupported_transport_modes: int
    non_journey_actions: int
    unknown_stations: int
    invalid_charges: int

    @property
    def skipped_count(self) -> int:
        return (self.unsupported_transport_modes
                + self.non_journey_actions
                + self.unknown_stations
                + self.invalid_charges)

class JourneyList(list[Journey]):
    def __init__(self,
                 journeys: list[Journey],
                 summary: JourneyLoadSummary,
                 ) -> None:
        super().__init__(journeys)
        self.summary = summary

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

def parse_endpoint_with_reason(
        endpoint: str,
        stations: dict[str, dict[str, str]],
        ) -> tuple[tuple[str, str] | None, str | None]:
    parsed = remove_marker(endpoint)
    if parsed is None:
        return None, UNSUPPORTED_TRANSPORT_MODE
    station, network = parsed
    if network == "unknown":
        return (station, network), None
    network_stations = stations.get(network)
    if network_stations is None:
        return None, UNSUPPORTED_TRANSPORT_MODE
    official_name = network_stations.get(key(station))
    if official_name is None:
        return None, UNKNOWN_STATION
    return (official_name, network), None

def parse_endpoint(endpoint: str,
                   stations: dict[str, dict[str, str]],
                   ) -> tuple[str, str] | None:
    parsed, _ = parse_endpoint_with_reason(endpoint, stations)
    return parsed

def clean_charge(value: object) -> str | None:
    text = clean_text(value).replace("£", "").replace(",", "")
    if not text:
        return None
    try:
        return str(float(text))
    except ValueError:
        return None

def clean_row_with_reason(
        row: dict[str, str],
        stations: dict[str, dict[str, str]],
        ) -> tuple[dict[str, str] | None, str | None]:
    action_text = row.get("Journey/Action", "")
    action = split_action(action_text)
    if action is None:
        if "journey" in key(action_text):
            return None, UNSUPPORTED_TRANSPORT_MODE
        return None, NON_JOURNEY_ACTION
    start, start_reason = parse_endpoint_with_reason(action[0], stations)
    end, end_reason = parse_endpoint_with_reason(action[1], stations)
    reasons = {start_reason, end_reason}
    if UNSUPPORTED_TRANSPORT_MODE in reasons:
        return None, UNSUPPORTED_TRANSPORT_MODE
    if UNKNOWN_STATION in reasons:
        return None, UNKNOWN_STATION
    charge = clean_charge(row.get("Charge", ""))
    if charge is None:
        return None, INVALID_CHARGE
    if start is None or end is None:
        return None, UNKNOWN_STATION
    start_station, start_network = start
    end_station, end_network = end
    return ({"date": clean_text(row.get("Date", "")),
             "start_time": clean_text(row.get("Start Time", "")),
             "end_time": clean_text(row.get("End Time", "")),
             "start_station": start_station,
             "end_station": end_station,
             "start_network": start_network,
             "end_network": end_network,
             "charged_amount": charge},
            None)

def clean_row(row: dict[str, str],
              stations: dict[str, dict[str, str]],
              ) -> dict[str, str] | None:
    cleaned, _ = clean_row_with_reason(row, stations)
    return cleaned

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

def load_raw_journeys_with_summary(
        reader: csv.DictReader,
        reference_dir: str | Path,
        ) -> tuple[list[Journey], JourneyLoadSummary]:
    stations = read_reference_data(Path(reference_dir))
    journeys = []
    skipped = {UNSUPPORTED_TRANSPORT_MODE: 0,
               NON_JOURNEY_ACTION: 0,
               UNKNOWN_STATION: 0,
               INVALID_CHARGE: 0}
    for row_number, row in enumerate(reader, start=2):
        cleaned, reason = clean_row_with_reason(row, stations)
        if cleaned is None:
            if reason is not None:
                skipped[reason] += 1
            continue
        journeys.append(journey_from_row(cleaned, row_number))
    summary = JourneyLoadSummary(
        loaded_count=len(journeys),
        unsupported_transport_modes=skipped[UNSUPPORTED_TRANSPORT_MODE],
        non_journey_actions=skipped[NON_JOURNEY_ACTION],
        unknown_stations=skipped[UNKNOWN_STATION],
        invalid_charges=skipped[INVALID_CHARGE])
    return journeys, summary

def load_raw_journeys(reader: csv.DictReader,
                      reference_dir: str | Path,
                      ) -> list[Journey]:
    journeys, _ = load_raw_journeys_with_summary(reader, reference_dir)
    return journeys

def load_journeys_with_summary(
        csv_path: str | Path,
        reference_dir: str | Path = REFERENCE_DIR,
        ) -> tuple[list[Journey], JourneyLoadSummary]:
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fields = set(reader.fieldnames or [])
        if not RAW_FIELDS.issubset(fields):
            raise JourneyParseError("CSV does not match the raw TfL format")
        journeys, summary = load_raw_journeys_with_summary(reader, reference_dir)
    if not journeys:
        raise JourneyParseError("No supported journeys were found in the CSV")
    return (sorted(journeys, key=lambda journey: journey.starts_at),
            summary)

def load_journeys(csv_path: str | Path,
                  reference_dir: str | Path = REFERENCE_DIR,
                  ) -> list[Journey]:
    journeys, summary = load_journeys_with_summary(csv_path, reference_dir)
    return JourneyList(journeys, summary)
