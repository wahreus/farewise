import csv
from pathlib import Path
import pytest
from src import ingest_data

def sample_stations() -> dict[str, dict[str, str]]:
    return {"underground": {
                "oxford circus": "Oxford Circus",
                "bank": "Bank"},
            "dlr": {
                "limehouse": "Limehouse"},
            "overground": {
                "surrey quays": "Surrey Quays"}}

def write_station_file(path: Path, station_name: str) -> None:
    path.write_text(
        f"Station,Line(s),Zone(s)\n{station_name},Example,1\n",
        encoding="utf-8")

def test_clean_text_normalizes_whitespace_and_none() -> None:
    assert ingest_data.clean_text("  Oxford   Circus \n") == "Oxford Circus"
    assert ingest_data.clean_text(None) == ""

def test_key_normalizes_whitespace_and_case() -> None:
    assert ingest_data.key("  OXFORD   Circus ") == "oxford circus"

def test_split_action_is_case_insensitive() -> None:
    assert ingest_data.split_action("Oxford Circus TO Bank") == (
        "Oxford Circus",
        "Bank")

def test_split_action_rejects_invalid_action() -> None:
    assert ingest_data.split_action("Oxford Circus") is None

@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [("Oxford Circus", ("Oxford Circus", "underground")),
     ("Limehouse DLR", ("Limehouse", "dlr")),
     ("Surrey Quays [London Overground]",
        ("Surrey Quays", "overground")),
     ("Oxford Circus [London Underground]",
        ("Oxford Circus", "underground")),
     ("Limehouse [DLR]", ("Limehouse", "dlr")),
     ("[No touch-out]", ("[No touch-out]", "unknown")),
     ("[No touch-in]", ("[No touch-in]", "unknown")),
     ("Station [Unsupported Network]", None)])
def test_remove_marker(endpoint: str, expected: tuple[str, str] | None,
    ) -> None:
    assert ingest_data.remove_marker(endpoint) == expected

def test_parse_endpoint_returns_official_station_name() -> None:
    assert ingest_data.parse_endpoint(
        "  OXFORD circus ",
        sample_stations(),
    ) == ("Oxford Circus", "underground")

def test_parse_endpoint_handles_incomplete_journey_marker() -> None:
    assert ingest_data.parse_endpoint(
        "[No touch-out]",
        sample_stations(),
    ) == ("[No touch-out]", "unknown")

def test_parse_endpoint_rejects_unknown_station() -> None:
    assert ingest_data.parse_endpoint(
        "Unknown Station",
        sample_stations(),
    ) is None

@pytest.mark.parametrize(("value", "expected"),
                         [("£2.80", "2.8"),
                         ("1,234.50", "1234.5"),
                         (2.5, "2.5"),
                         ("", None),
                         (None, None),
                         ("not a charge", None)])
def test_clean_charge(value: object, expected: str | None) -> None:
    assert ingest_data.clean_charge(value) == expected


def test_clean_row_returns_normalized_journey() -> None:
    row = {"Date": "01/03/2026",
           "Start Time": "08:10",
           "End Time": "08:25",
           "Journey/Action": "Oxford Circus to Limehouse DLR",
           "Charge": "£2.80"}
    cleaned = ingest_data.clean_row(row, sample_stations())
    assert cleaned == {"date": "01/03/2026",
                       "start_time": "08:10",
                       "end_time": "08:25",
                       "start_station": "Oxford Circus",
                       "end_station": "Limehouse",
                       "start_network": "underground",
                       "end_network": "dlr",
                       "charged_amount": "2.8"}

def test_clean_row_rejects_invalid_journey() -> None:
    row = {"Date": "01/03/2026",
           "Start Time": "08:10",
           "End Time": "08:25",
           "Journey/Action": "Oxford Circus to Unknown Station",
           "Charge": "£2.80"}
    assert ingest_data.clean_row(row, sample_stations()) is None

def test_read_station_names_uses_normalized_keys(tmp_path) -> None:
    station_path = tmp_path / "stations.csv"
    station_path.write_text("Station,Line(s),Zone(s)\n"
                            "Oxford Circus,Central | Victoria,1\n"
                            "  Earl's   Court  ,District | Piccadilly,1 | 2\n",
                            encoding="utf-8-sig")
    stations = ingest_data.read_station_names(station_path)
    assert stations == {"oxford circus": "Oxford Circus",
                        "earl's court": "Earl's Court"}

def test_read_reference_data_loads_all_network_files(tmp_path) -> None:
    write_station_file(tmp_path / "london_underground_stations.csv",
                       "Oxford Circus")
    write_station_file(tmp_path / "london_dlr_stations.csv", "Limehouse")
    write_station_file(tmp_path / "london_overground_stations.csv",
                       "Surrey Quays")
    stations = ingest_data.read_reference_data(tmp_path)
    assert stations == {"underground": {"oxford circus": "Oxford Circus"},
                        "dlr": {"limehouse": "Limehouse"},
                        "overground": {"surrey quays": "Surrey Quays"}}

def test_find_repo_root_finds_parent_repository(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "farewise"
    script_dir = repo_root / "src" / "nested"
    script_dir.mkdir(parents=True)
    (repo_root / "data" / "raw").mkdir(parents=True)
    (repo_root / "data" / "reference").mkdir(parents=True)
    (repo_root / "data" / "raw" / "journey_history.csv").touch()
    monkeypatch.setattr(ingest_data, "__file__",
                        str(script_dir / "ingest_data.py"))
    assert ingest_data.find_repo_root() == repo_root

def test_find_repo_root_raises_when_repository_is_missing(tmp_path,
                                                          monkeypatch,
                                                          ) -> None:
    script_path = tmp_path / "src" / "ingest_data.py"
    script_path.parent.mkdir()
    monkeypatch.setattr(ingest_data, "__file__", str(script_path))
    with pytest.raises(FileNotFoundError):
        ingest_data.find_repo_root()

def test_main_writes_only_valid_cleaned_rows(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "farewise"
    raw_dir = repo_root / "data" / "raw"
    reference_dir = repo_root / "data" / "reference"
    raw_dir.mkdir(parents=True)
    reference_dir.mkdir(parents=True)
    write_station_file(reference_dir / "london_underground_stations.csv",
                       "Oxford Circus")
    write_station_file(reference_dir / "london_dlr_stations.csv",
                       "Limehouse")
    write_station_file(reference_dir / "london_overground_stations.csv",
                       "Surrey Quays")
    input_path = raw_dir / "journey_history.csv"
    with input_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file,
                                fieldnames=["Date",
                                            "Start Time",
                                            "End Time",
                                            "Journey/Action",
                                            "Charge"])
        writer.writeheader()
        writer.writerow({"Date": "01/03/2026",
                         "Start Time": "08:10",
                         "End Time": "08:25",
                         "Journey/Action": "Oxford Circus to Limehouse DLR",
                         "Charge": "£2.80"})
        writer.writerow({"Date": "01/03/2026",
                         "Start Time": "09:00",
                         "End Time": "09:10",
                         "Journey/Action": "Oxford Circus to Unknown Station",
                         "Charge": "£2.80"})
    monkeypatch.setattr(ingest_data, "find_repo_root", lambda: repo_root)
    ingest_data.main()
    output_path = repo_root / "data" / "processed" / "journey_history_processed.csv"
    with output_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows == [{"date": "01/03/2026",
                     "start_time": "08:10",
                     "end_time": "08:25",
                     "start_station": "Oxford Circus",
                     "end_station": "Limehouse",
                     "start_network": "underground",
                     "end_network": "dlr",
                     "charged_amount": "2.8"}]
