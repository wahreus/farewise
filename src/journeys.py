import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from src.ingest_data import clean_row, read_reference_data

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
DATE_FORMATS = ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
TIME_FORMATS = ("%H:%M", "%H:%M:%S")
PROCESSED_FIELDS = {"date",
                    "start_time",
                    "end_time",
                    "start_station",
                    "end_station",
                    "start_network",
                    "end_network",
                    "charged_amount"}
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
        raise JourneyParseError(f"Invalid processed journey{location}: {error}") from error

def load_processed_journeys(reader: csv.DictReader) -> list[Journey]:
    return [journey_from_row(row, row_number)
            for row_number, row in enumerate(reader, start=2)]

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
        if PROCESSED_FIELDS.issubset(fields):
            journeys = load_processed_journeys(reader)
        elif RAW_FIELDS.issubset(fields):
            journeys = load_raw_journeys(reader, reference_dir)
        else:
            raise JourneyParseError(
                "CSV does not match the raw TfL or processed FareWise format")
    if not journeys:
        raise JourneyParseError("No supported journeys were found in the CSV")
    return sorted(journeys, key=lambda journey: journey.starts_at)
