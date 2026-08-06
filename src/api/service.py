"""Application service connecting the API to the FareWise engine."""

from decimal import Decimal
from pathlib import Path
from typing import Protocol

from src.api.models import (AnalysisResponse,
                            InputSummaryResponse,
                            PaygSelectionResponse,
                            PaymentSelectionResponse,
                            TravelcardSelectionResponse)
from src.coverage import REFERENCE_DIR, load_station_lookup
from src.fares import FARES_JSON, load_fare_data
from src.journeys import JourneyLoadSummary, load_journeys
from src.optimizer import optimize_fares
from src.results import (OptimizationResult,
                         PaygSelection,
                         TravelcardSelection)


def format_amount(value: Decimal) -> str:
    """Format money as an exact two-decimal string for JSON responses."""
    return f"{value:.2f}"


def build_input_summary(
        summary: JourneyLoadSummary | None,
        ) -> InputSummaryResponse | None:
    """Convert a journey-loading summary into an API response model."""
    if summary is None:
        return None
    return InputSummaryResponse(
        loaded_journeys=summary.loaded_count,
        skipped_rows=summary.skipped_count,
        unsupported_transport_modes=summary.unsupported_transport_modes,
        non_journey_actions=summary.non_journey_actions,
        unknown_stations=summary.unknown_stations,
        invalid_charges=summary.invalid_charges)


def build_selection_response(
        selection: PaygSelection | TravelcardSelection,
        ) -> PaymentSelectionResponse:
    """Convert one optimiser selection into its API representation."""
    if isinstance(selection, PaygSelection):
        return PaygSelectionResponse(
            start_date=selection.start_date,
            end_date=selection.end_date,
            total_cost=format_amount(selection.total_cost),
            journey_count=selection.journey_count)
    return TravelcardSelectionResponse(
        product_name=selection.product_name,
        zone_name=selection.zone_name,
        max_zone=selection.max_zone,
        start_date=selection.start_date,
        end_date=selection.end_date,
        card_cost=format_amount(selection.card_cost),
        outside_payg_cost=format_amount(selection.outside_payg_cost),
        total_cost=format_amount(selection.total_cost),
        covered_journey_count=selection.covered_journey_count,
        uncovered_journey_count=selection.uncovered_journey_count)


def build_analysis_response(
        result: OptimizationResult,
        summary: JourneyLoadSummary | None,
        ) -> AnalysisResponse:
    """Convert the FareWise domain result into a stable HTTP response."""
    return AnalysisResponse(
        journey_start_date=result.journey_start_date,
        journey_end_date=result.journey_end_date,
        recorded_payg_total=format_amount(result.payg_total),
        optimized_total=format_amount(result.optimized_total),
        estimated_saving=format_amount(result.savings),
        uses_travelcard=result.uses_travelcard,
        input_summary=build_input_summary(summary),
        selections=[build_selection_response(selection)
                    for selection in result.selections],
        warnings=list(result.warnings))


class AnalysisService(Protocol):
    """Operations required by the HTTP layer."""

    def analyze_file(self, csv_path: Path) -> AnalysisResponse:
        """Analyse one uploaded journey-history file."""

    def is_ready(self) -> bool:
        """Return whether required FareWise reference data is available."""


class FareWiseAnalysisService:
    """Run the existing FareWise engine for API requests."""

    def __init__(self,
                 fares_path: Path = FARES_JSON,
                 reference_dir: Path = REFERENCE_DIR,
                 ) -> None:
        self.fares_path = fares_path
        self.reference_dir = reference_dir

    def is_ready(self) -> bool:
        """Check that the static fare and station data can be reached."""
        return self.fares_path.is_file() and self.reference_dir.is_dir()

    def analyze_file(self, csv_path: Path) -> AnalysisResponse:
        """Load, optimise and serialize one journey-history CSV."""
        journeys = load_journeys(csv_path, self.reference_dir)
        stations = load_station_lookup(self.reference_dir)
        fare_data = load_fare_data(self.fares_path)
        result = optimize_fares(journeys, stations, fare_data)
        summary = getattr(journeys, "summary", None)
        return build_analysis_response(result, summary)
