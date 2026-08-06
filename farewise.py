"""Command-line entry point for FareWise."""

import argparse
import sys
from pathlib import Path

from src.coverage import REFERENCE_DIR, load_station_lookup
from src.fares import FARES_JSON, load_fare_data
from src.journeys import JourneyLoadSummary, load_journeys
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


def count_label(count: int, singular: str, plural: str) -> str:
    """Format a count with the appropriate singular or plural label."""
    label = singular if count == 1 else plural
    return f"{count} {label}"


def print_journey_summary(summary: JourneyLoadSummary) -> None:
    """Print the number of loaded journeys and categorized skipped rows."""
    print(f"\nSkipped {summary.skipped_count} CSV rows:")
    if summary.unsupported_transport_modes:
        print("- " + count_label(summary.unsupported_transport_modes,
                                 "unsupported transport mode",
                                 "unsupported transport modes"))
    if summary.non_journey_actions:
        print("- " + count_label(summary.non_journey_actions,
                                 "non-journey action",
                                 "non-journey actions"))
    if summary.unknown_stations:
        print("- " + count_label(summary.unknown_stations,
                                 "unknown station",
                                 "unknown stations"))
    if summary.invalid_charges:
        print("- " + count_label(summary.invalid_charges,
                                 "invalid charge",
                                 "invalid charges"))
    print(f"Loaded {summary.loaded_count} supported journeys.")


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
    summary = getattr(journeys, "summary", None)
    if summary is not None:
        print_journey_summary(summary)
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
