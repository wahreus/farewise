from pathlib import Path

import pytest

import farewise


def test_build_parser_uses_default_fare_and_reference_paths() -> None:
    args = farewise.build_parser().parse_args(["journeys.csv"])
    assert args.journey_file == Path("journeys.csv")
    assert args.fares == farewise.FARES_JSON
    assert args.reference_dir == farewise.REFERENCE_DIR


def test_build_parser_accepts_custom_fare_and_reference_paths() -> None:
    args = farewise.build_parser().parse_args(
        ["journeys.csv",
         "--fares", "custom_fares.json",
         "--reference-dir", "custom_reference"])
    assert args.journey_file == Path("journeys.csv")
    assert args.fares == Path("custom_fares.json")
    assert args.reference_dir == Path("custom_reference")


def test_main_runs_complete_fare_comparison(monkeypatch, tmp_path) -> None:
    journey_path = tmp_path / "journeys.csv"
    fare_path = tmp_path / "fares.json"
    reference_dir = tmp_path / "reference"
    journeys = [object()]
    stations = {("underground", "bank"): object()}
    fare_data = object()
    result = object()
    printed_results = []

    def fake_load_journeys(path: Path,
                           loaded_reference_dir: Path,
                           ) -> list[object]:
        assert path == journey_path
        assert loaded_reference_dir == reference_dir
        return journeys

    def fake_load_station_lookup(path: Path) -> dict:
        assert path == reference_dir
        return stations

    def fake_load_fare_data(path: Path) -> object:
        assert path == fare_path
        return fare_data

    def fake_optimize_fares(loaded_journeys: list[object],
                            loaded_stations: dict,
                            loaded_fare_data: object,
                            ) -> object:
        assert loaded_journeys is journeys
        assert loaded_stations is stations
        assert loaded_fare_data is fare_data
        return result

    monkeypatch.setattr(
        "sys.argv",
        ["farewise.py",
         str(journey_path),
         "--fares", str(fare_path),
         "--reference-dir", str(reference_dir)])
    monkeypatch.setattr(farewise, "load_journeys", fake_load_journeys)
    monkeypatch.setattr(farewise,
                        "load_station_lookup",
                        fake_load_station_lookup)
    monkeypatch.setattr(farewise, "load_fare_data", fake_load_fare_data)
    monkeypatch.setattr(farewise, "optimize_fares", fake_optimize_fares)
    monkeypatch.setattr(farewise,
                        "print_report",
                        lambda printed_result: printed_results.append(
                            printed_result))

    assert farewise.main() == 0
    assert printed_results == [result]


@pytest.mark.parametrize(
    "error",
    [FileNotFoundError("missing file"),
     OSError("read failed"),
     ValueError("invalid value"),
     KeyError("missing key")])
def test_main_prints_supported_errors(error: Exception,
                                      monkeypatch,
                                      capsys,
                                      ) -> None:
    monkeypatch.setattr("sys.argv", ["farewise.py", "journeys.csv"])

    def raise_error(*_args, **_kwargs) -> None:
        raise error

    monkeypatch.setattr(farewise, "load_journeys", raise_error)

    assert farewise.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"FareWise error: {error}\n"
