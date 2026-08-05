import csv
from datetime import date, datetime, time
from decimal import Decimal
from io import StringIO
from pathlib import Path
import pytest
from src import journeys

def processed_row(**overrides: str) -> dict[str, str]:
    row = {"date": "01/03/2026",
           "start_time": "08:10",
           "end_time": "08:25",
           "start_station": "Oxford Circus",
           "end_station": "Bank",
           "start_network": "Underground",
           "end_network": "UNDERGROUND",
           "charged_amount": "£2.80"}
    row.update(overrides)
    return row

def write_reference_files(reference_dir: Path) -> None:
    reference_dir.mkdir(parents=True, exist_ok=True)
    station_files = {
        "london_underground_stations.csv": ["Oxford Circus", "Bank"],
        "london_dlr_stations.csv": ["Limehouse"],
        "london_overground_stations.csv": ["Surrey Quays"]}
    for filename, station_names in station_files.items():
        path = reference_dir / filename
        path.write_text(
            "Station,Line(s),Zone(s)\n"
            + "".join(f"{station_name},Example,1\n"
                      for station_name in station_names),
            encoding="utf-8")

def write_csv(path: Path,
              fieldnames: list[str],
              rows: list[dict[str, str]],
              ) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def test_journey_starts_at_combines_date_and_start_time() -> None:
    journey = journeys.Journey(
        date=date(2026, 3, 1),
        start_time=time(8, 10),
        end_time=time(8, 25),
        start_station="Oxford Circus",
        end_station="Bank",
        start_network="underground",
        end_network="underground",
        charged_amount=Decimal("2.80"))
    assert journey.starts_at == datetime(2026, 3, 1, 8, 10)

@pytest.mark.parametrize(
    ("value", "expected"),
    [("01-Mar-2026", date(2026, 3, 1)),
     ("2026-03-01", date(2026, 3, 1)),
     ("01/03/2026", date(2026, 3, 1)),
     ("01-03-2026", date(2026, 3, 1)),
     (" 01/03/2026 ", date(2026, 3, 1))])
def test_parse_date_accepts_supported_formats(value: str,
                                              expected: date,
                                              ) -> None:
    assert journeys.parse_date(value) == expected

def test_parse_date_rejects_unsupported_format() -> None:
    with pytest.raises(journeys.JourneyParseError,
                       match="Unsupported journey date"):
        journeys.parse_date("March 1, 2026")

@pytest.mark.parametrize(
    ("value", "expected"),
    [("08:10", time(8, 10)),
     ("08:10:45", time(8, 10, 45)),
     (" 08:10 ", time(8, 10))])
def test_parse_time_accepts_supported_formats(value: str,
                                              expected: time,
                                              ) -> None:
    assert journeys.parse_time(value) == expected

def test_parse_time_rejects_invalid_time() -> None:
    with pytest.raises(journeys.JourneyParseError,
                       match="Unsupported journey time"):
        journeys.parse_time("25:00")

def test_parse_optional_time_returns_none_for_blank_value() -> None:
    assert journeys.parse_optional_time("") is None
    assert journeys.parse_optional_time("   ") is None

def test_parse_optional_time_parses_non_blank_value() -> None:
    assert journeys.parse_optional_time("08:25") == time(8, 25)

@pytest.mark.parametrize(
    ("value", "expected"),
    [("2.80", Decimal("2.80")),
     ("£2.80", Decimal("2.80")),
     ("1,234.50", Decimal("1234.50")),
     (" -1.50 ", Decimal("-1.50"))])
def test_parse_amount_accepts_supported_values(value: str,
                                               expected: Decimal,
                                               ) -> None:
    assert journeys.parse_amount(value) == expected

def test_parse_amount_rejects_invalid_value() -> None:
    with pytest.raises(journeys.JourneyParseError,
                       match="Unsupported journey charge"):
        journeys.parse_amount("not a charge")

def test_journey_from_row_creates_typed_journey() -> None:
    journey = journeys.journey_from_row(processed_row())
    assert journey == journeys.Journey(
        date=date(2026, 3, 1),
        start_time=time(8, 10),
        end_time=time(8, 25),
        start_station="Oxford Circus",
        end_station="Bank",
        start_network="underground",
        end_network="underground",
        charged_amount=Decimal("2.80"))

def test_journey_from_row_allows_missing_end_time() -> None:
    journey = journeys.journey_from_row(processed_row(end_time=""))
    assert journey.end_time is None

def test_journey_from_row_strips_names_and_normalizes_networks() -> None:
    journey = journeys.journey_from_row(
        processed_row(start_station="  Oxford Circus  ",
                      end_station=" Bank ",
                      start_network=" UNDERGROUND ",
                      end_network=" Underground "))
    assert journey.start_station == "Oxford Circus"
    assert journey.end_station == "Bank"
    assert journey.start_network == "underground"
    assert journey.end_network == "underground"

@pytest.mark.parametrize(
    ("overrides", "message"),
    [({"start_station": ""}, "Station names cannot be empty"),
     ({"end_station": "   "}, "Station names cannot be empty"),
     ({"start_network": ""}, "Network names cannot be empty"),
     ({"end_network": "   "}, "Network names cannot be empty"),
     ({"date": "bad date"}, "Unsupported journey date"),
     ({"start_time": "bad time"}, "Unsupported journey time"),
     ({"charged_amount": "bad amount"}, "Unsupported journey charge")])
def test_journey_from_row_rejects_invalid_values(
    overrides: dict[str, str],
    message: str,
    ) -> None:
    with pytest.raises(journeys.JourneyParseError, match=message):
        journeys.journey_from_row(processed_row(**overrides))

def test_journey_from_row_reports_csv_row_number() -> None:
    row = processed_row()
    del row["date"]
    with pytest.raises(journeys.JourneyParseError,
                       match="Invalid processed journey at CSV row 7"):
        journeys.journey_from_row(row, row_number=7)

def test_load_processed_journeys_loads_every_row() -> None:
    content = StringIO(
        "date,start_time,end_time,start_station,end_station,"
        "start_network,end_network,charged_amount\n"
        "01/03/2026,08:10,08:25,Oxford Circus,Bank,"
        "underground,underground,2.80\n"
        "01/03/2026,09:00,09:20,Bank,Oxford Circus,"
        "underground,underground,3.00\n")
    loaded = journeys.load_processed_journeys(csv.DictReader(content))
    assert len(loaded) == 2
    assert loaded[0].start_station == "Oxford Circus"
    assert loaded[1].charged_amount == Decimal("3.00")

def test_load_raw_journeys_cleans_and_skips_unsupported_rows(
    tmp_path: Path,
    ) -> None:
    reference_dir = tmp_path / "reference"
    write_reference_files(reference_dir)
    content = StringIO(
        "Date,Start Time,End Time,Journey/Action,Charge\n"
        "01/03/2026,08:10,08:25,Oxford Circus to Limehouse DLR,£2.80\n"
        "01/03/2026,09:00,09:15,Oxford Circus to Unknown Station,£2.80\n")
    loaded = journeys.load_raw_journeys(csv.DictReader(content),
                                        reference_dir)
    assert loaded == [
        journeys.Journey(
            date=date(2026, 3, 1),
            start_time=time(8, 10),
            end_time=time(8, 25),
            start_station="Oxford Circus",
            end_station="Limehouse",
            start_network="underground",
            end_network="dlr",
            charged_amount=Decimal("2.8"))]

def test_load_journeys_loads_processed_csv_and_sorts_it(
    tmp_path: Path,
    ) -> None:
    csv_path = tmp_path / "processed.csv"
    write_csv(
        csv_path,
        list(journeys.PROCESSED_FIELDS),
        [processed_row(date="02/03/2026",
                       start_time="09:00",
                       end_time="09:15"),
         processed_row(date="01/03/2026",
                       start_time="10:00",
                       end_time="10:15"),
         processed_row(date="01/03/2026",
                       start_time="08:00",
                       end_time="08:15")])
    loaded = journeys.load_journeys(csv_path)
    assert [journey.starts_at for journey in loaded] == [
        datetime(2026, 3, 1, 8, 0),
        datetime(2026, 3, 1, 10, 0),
        datetime(2026, 3, 2, 9, 0)]

def test_load_journeys_accepts_additional_processed_columns(
    tmp_path: Path,
    ) -> None:
    csv_path = tmp_path / "processed.csv"
    fieldnames = list(journeys.PROCESSED_FIELDS) + ["extra"]
    row = processed_row()
    row["extra"] = "ignored"
    write_csv(csv_path, fieldnames, [row])
    loaded = journeys.load_journeys(csv_path)
    assert len(loaded) == 1

def test_load_journeys_loads_raw_csv(tmp_path: Path) -> None:
    reference_dir = tmp_path / "reference"
    write_reference_files(reference_dir)
    csv_path = tmp_path / "raw.csv"
    write_csv(
        csv_path,
        list(journeys.RAW_FIELDS),
        [{"Date": "01/03/2026",
          "Start Time": "08:10",
          "End Time": "08:25",
          "Journey/Action": "Oxford Circus to Limehouse DLR",
          "Charge": "£2.80"}])
    loaded = journeys.load_journeys(csv_path, reference_dir)
    assert len(loaded) == 1
    assert loaded[0].end_station == "Limehouse"
    assert loaded[0].end_network == "dlr"

def test_load_journeys_rejects_unknown_csv_format(tmp_path: Path) -> None:
    csv_path = tmp_path / "unknown.csv"
    csv_path.write_text("name,value\nexample,1\n", encoding="utf-8")
    with pytest.raises(journeys.JourneyParseError,
                       match="CSV does not match"):
        journeys.load_journeys(csv_path)

def test_load_journeys_rejects_empty_processed_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "empty.csv"
    write_csv(csv_path, list(journeys.PROCESSED_FIELDS), [])
    with pytest.raises(journeys.JourneyParseError,
                       match="No supported journeys were found"):
        journeys.load_journeys(csv_path)

def test_load_journeys_rejects_raw_csv_without_supported_rows(
    tmp_path: Path,
    ) -> None:
    reference_dir = tmp_path / "reference"
    write_reference_files(reference_dir)
    csv_path = tmp_path / "raw.csv"
    write_csv(
        csv_path,
        list(journeys.RAW_FIELDS),
        [{"Date": "01/03/2026",
          "Start Time": "08:10",
          "End Time": "08:25",
          "Journey/Action": "Oxford Circus to Unknown Station",
          "Charge": "£2.80"}])
    with pytest.raises(journeys.JourneyParseError,
                       match="No supported journeys were found"):
        journeys.load_journeys(csv_path, reference_dir)
