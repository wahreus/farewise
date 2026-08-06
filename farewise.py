"""Command-line entry point for FareWise."""

import argparse
import sys
from pathlib import Path

from src.coverage import REFERENCE_DIR, load_station_lookup
from src.fares import FARES_JSON, load_fare_data
from src.journeys import load_journeys
from src.optimizer import optimize_fares
from src.report import print_report


def build_parser() -> argparse.ArgumentParser:
    """Build the FareWise command-line parser."""
    parser = argparse.ArgumentParser(
        description="Compare recorded TfL PAYG charges with Travelcards")
    parser.add_argument(
        "journey_file",
        type=Path,
        help="Raw TfL journey history CSV")
    parser.add_argument(
        "--fares",
        type=Path,
        default=FARES_JSON,
        help=f"Fare JSON file (default: {FARES_JSON})")
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=REFERENCE_DIR,
        help=f"Station reference directory (default: {REFERENCE_DIR})")
    return parser


def main() -> int:
    """Run the complete FareWise comparison."""
    args = build_parser().parse_args()
    try:
        journeys = load_journeys(args.journey_file, args.reference_dir)
        stations = load_station_lookup(args.reference_dir)
        fare_data = load_fare_data(args.fares)
        result = optimize_fares(journeys, stations, fare_data)
    except (FileNotFoundError, OSError, ValueError, KeyError) as error:
        print(f"FareWise error: {error}", file=sys.stderr)
        return 1
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
