"""Tests for journey parsing, normalization, validation, and loading."""

import csv
from datetime import date, datetime, time
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from src import journeys


def normalized_row(**overrides: str) -> dict[str, str]:
    """Return a valid normalized journey row with optional overrides."""
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


def sample_stations() -> dict[str, dict[str, str]]:
    """Return representative station names grouped by network."""
    return {"underground": {
                "oxford circus": "Oxford Circus",
                "bank": "Bank"},
            "dlr": {
                "limehouse": "Limehouse"},
            "overground": {
                "surrey quays": "Surrey Quays"}}


def write_reference_files(reference_dir: Path) -> None:
    """Write minimal station reference files for supported networks."""
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
    """Write rows to a CSV file using the supplied field names."""
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def raw_row(date_value: str = "01/03/2026",
            start_time: str = "08:10",
            end_time: str = "08:25",
            action: str = "Oxford Circus to Limehouse DLR",
            charge: str = "£2.80",
            ) -> dict[str, str]:
    """Return a representative raw TfL journey row."""
    return {"Date": date_value,
            "Start Time": start_time,
            "End Time": end_time,
            "Journey/Action": action,
            "Charge": charge}


def test_journey_starts_at_combines_date_and_start_time() -> None:
    """Verify that journey starts at combines date and start time."""
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


def test_clean_text_normalizes_whitespace_and_none() -> None:
    """Verify that clean text normalizes whitespace and none."""
    assert journeys.clean_text("  Oxford   Circus \n") == "Oxford Circus"
    assert journeys.clean_text(None) == ""


def test_key_normalizes_whitespace_and_case() -> None:
    """Verify that key normalizes whitespace and case."""
    assert journeys.key("  OXFORD   Circus ") == "oxford circus"


def test_read_station_names_uses_normalized_keys(tmp_path: Path) -> None:
    """Verify that read station names uses normalized keys."""
    station_path = tmp_path / "stations.csv"
    station_path.write_text("Station,Line(s),Zone(s)\n"
                            "Oxford Circus,Central | Victoria,1\n"
                            "  Earl's   Court  ,District | Piccadilly,1 | 2\n",
                            encoding="utf-8-sig")
    stations = journeys.read_station_names(station_path)
    assert stations == {"oxford circus": "Oxford Circus",
                        "earl's court": "Earl's Court"}


def test_read_reference_data_loads_all_network_files(tmp_path: Path) -> None:
    """Verify that read reference data loads all network files."""
    write_reference_files(tmp_path)
    stations = journeys.read_reference_data(tmp_path)
    assert stations == sample_stations()


def test_split_action_is_case_insensitive() -> None:
    """Verify that split action is case insensitive."""
    assert journeys.split_action("Oxford Circus TO Bank") == (
        "Oxford Circus",
        "Bank")


def test_split_action_rejects_invalid_action() -> None:
    """Verify that split action rejects invalid action."""
    assert journeys.split_action("Oxford Circus") is None


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [("Oxford Circus", ("Oxford Circus", "underground")),
     ("Limehouse DLR", ("Limehouse", "dlr")),
     ("Surrey Quays [London Overground]", ("Surrey Quays", "overground")),
     ("Oxford Circus [London Underground]",
      ("Oxford Circus", "underground")),
     ("Limehouse [DLR]", ("Limehouse", "dlr")),
     ("[No touch-out]", ("[No touch-out]", "unknown")),
     ("[No touch-in]", ("[No touch-in]", "unknown")),
     ("Station [Unsupported Network]", None)])
def test_remove_marker(endpoint: str,
                       expected: tuple[str, str] | None,
                       ) -> None:
    """Verify that endpoint markers map to the expected transport network."""
    assert journeys.remove_marker(endpoint) == expected


def test_parse_endpoint_returns_official_station_name() -> None:
    """Verify that parse endpoint returns official station name."""
    assert journeys.parse_endpoint(
        "  OXFORD circus ",
        sample_stations(),
    ) == ("Oxford Circus", "underground")


def test_parse_endpoint_handles_incomplete_journey_marker() -> None:
    """Verify that parse endpoint handles incomplete journey marker."""
    assert journeys.parse_endpoint(
        "[No touch-out]",
        sample_stations(),
    ) == ("[No touch-out]", "unknown")


def test_parse_endpoint_rejects_unknown_station() -> None:
    """Verify that parse endpoint rejects unknown station."""
    assert journeys.parse_endpoint(
        "Unknown Station",
        sample_stations(),
    ) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("£2.80", "2.8"),
     ("1,234.50", "1234.5"),
     (2.5, "2.5"),
     ("", None),
     (None, None),
     ("not a charge", None)])
def test_clean_charge(value: object, expected: str | None) -> None:
    """Verify that raw charge values are normalized or rejected as expected."""
    assert journeys.clean_charge(value) == expected


def test_clean_row_returns_normalized_journey() -> None:
    """Verify that clean row returns normalized journey."""
    cleaned = journeys.clean_row(raw_row(), sample_stations())
    assert cleaned == {"date": "01/03/2026",
                       "start_time": "08:10",
                       "end_time": "08:25",
                       "start_station": "Oxford Circus",
                       "end_station": "Limehouse",
                       "start_network": "underground",
                       "end_network": "dlr",
                       "charged_amount": "2.8"}


def test_clean_row_rejects_invalid_journey() -> None:
    """Verify that clean row rejects invalid journey."""
    row = raw_row(action="Oxford Circus to Unknown Station")
    assert journeys.clean_row(row, sample_stations()) is None


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
    """Verify that parse date accepts supported formats."""
    assert journeys.parse_date(value) == expected


def test_parse_date_rejects_unsupported_format() -> None:
    """Verify that parse date rejects unsupported format."""
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
    """Verify that parse time accepts supported formats."""
    assert journeys.parse_time(value) == expected


def test_parse_time_rejects_invalid_time() -> None:
    """Verify that parse time rejects invalid time."""
    with pytest.raises(journeys.JourneyParseError,
                       match="Unsupported journey time"):
        journeys.parse_time("25:00")


def test_parse_optional_time_returns_none_for_blank_value() -> None:
    """Verify that parse optional time returns none for blank value."""
    assert journeys.parse_optional_time("") is None
    assert journeys.parse_optional_time("   ") is None


def test_parse_optional_time_parses_non_blank_value() -> None:
    """Verify that parse optional time parses non blank value."""
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
    """Verify that parse amount accepts supported values."""
    assert journeys.parse_amount(value) == expected


def test_parse_amount_rejects_invalid_value() -> None:
    """Verify that parse amount rejects invalid value."""
    with pytest.raises(journeys.JourneyParseError,
                       match="Unsupported journey charge"):
        journeys.parse_amount("not a charge")


def test_journey_from_row_creates_typed_journey() -> None:
    """Verify that journey from row creates typed journey."""
    journey = journeys.journey_from_row(normalized_row())
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
    """Verify that journey from row allows missing end time."""
    journey = journeys.journey_from_row(normalized_row(end_time=""))
    assert journey.end_time is None


def test_journey_from_row_strips_names_and_normalizes_networks() -> None:
    """Verify that journey from row strips names and normalizes networks."""
    journey = journeys.journey_from_row(
        normalized_row(start_station="  Oxford Circus  ",
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
    """Verify that invalid normalized rows raise the expected parsing errors."""
    with pytest.raises(journeys.JourneyParseError, match=message):
        journeys.journey_from_row(normalized_row(**overrides))


def test_journey_from_row_reports_csv_row_number() -> None:
    """Verify that journey from row reports CSV row number."""
    row = normalized_row()
    del row["date"]
    with pytest.raises(journeys.JourneyParseError,
                       match="Invalid journey at CSV row 7"):
        journeys.journey_from_row(row, row_number=7)


def test_load_raw_journeys_cleans_and_skips_unsupported_rows(
    tmp_path: Path,
    ) -> None:
    """Verify that load raw journeys cleans and skips unsupported rows."""
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


def test_load_journeys_loads_raw_csv_and_sorts_it(tmp_path: Path) -> None:
    """Verify that load journeys loads raw CSV and sorts it."""
    reference_dir = tmp_path / "reference"
    write_reference_files(reference_dir)
    csv_path = tmp_path / "raw.csv"
    write_csv(
        csv_path,
        list(journeys.RAW_FIELDS),
        [raw_row(date_value="02/03/2026", start_time="09:00"),
         raw_row(date_value="01/03/2026", start_time="10:00"),
         raw_row(date_value="01/03/2026", start_time="08:00")])
    loaded = journeys.load_journeys(csv_path, reference_dir)
    assert [journey.starts_at for journey in loaded] == [
        datetime(2026, 3, 1, 8, 0),
        datetime(2026, 3, 1, 10, 0),
        datetime(2026, 3, 2, 9, 0)]


def test_load_journeys_accepts_additional_raw_columns(tmp_path: Path) -> None:
    """Verify that load journeys accepts additional raw columns."""
    reference_dir = tmp_path / "reference"
    write_reference_files(reference_dir)
    csv_path = tmp_path / "raw.csv"
    fieldnames = list(journeys.RAW_FIELDS) + ["Extra"]
    row = raw_row()
    row["Extra"] = "ignored"
    write_csv(csv_path, fieldnames, [row])
    loaded = journeys.load_journeys(csv_path, reference_dir)
    assert len(loaded) == 1


def test_load_journeys_rejects_processed_csv(tmp_path: Path) -> None:
    """Verify that load journeys rejects processed CSV."""
    csv_path = tmp_path / "processed.csv"
    write_csv(csv_path, list(normalized_row()), [normalized_row()])
    with pytest.raises(journeys.JourneyParseError,
                       match="raw TfL format"):
        journeys.load_journeys(csv_path)


def test_load_journeys_rejects_unknown_csv_format(tmp_path: Path) -> None:
    """Verify that load journeys rejects unknown CSV format."""
    csv_path = tmp_path / "unknown.csv"
    csv_path.write_text("name,value\nexample,1\n", encoding="utf-8")
    with pytest.raises(journeys.JourneyParseError,
                       match="CSV does not match"):
        journeys.load_journeys(csv_path)


def test_load_journeys_rejects_empty_raw_csv(tmp_path: Path) -> None:
    """Verify that load journeys rejects empty raw CSV."""
    reference_dir = tmp_path / "reference"
    write_reference_files(reference_dir)
    csv_path = tmp_path / "empty.csv"
    write_csv(csv_path, list(journeys.RAW_FIELDS), [])
    with pytest.raises(journeys.JourneyParseError,
                       match="No supported journeys were found"):
        journeys.load_journeys(csv_path, reference_dir)


def test_load_journeys_rejects_raw_csv_without_supported_rows(
    tmp_path: Path,
    ) -> None:
    """Verify that load journeys rejects raw CSV without supported rows."""
    reference_dir = tmp_path / "reference"
    write_reference_files(reference_dir)
    csv_path = tmp_path / "raw.csv"
    write_csv(
        csv_path,
        list(journeys.RAW_FIELDS),
        [raw_row(action="Oxford Circus to Unknown Station")])
    with pytest.raises(journeys.JourneyParseError,
                       match="No supported journeys were found"):
        journeys.load_journeys(csv_path, reference_dir)
