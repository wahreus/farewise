"""Response models exposed by the FareWise API."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class InputSummaryResponse(BaseModel):
    """Summary of accepted and skipped rows in the uploaded CSV."""

    loaded_journeys: int
    skipped_rows: int
    unsupported_transport_modes: int
    non_journey_actions: int
    unknown_stations: int
    invalid_charges: int


class PaygSelectionResponse(BaseModel):
    """A PAYG period selected by the optimiser."""

    payment_type: Literal["payg"] = "payg"
    start_date: date
    end_date: date
    total_cost: str
    journey_count: int


class TravelcardSelectionResponse(BaseModel):
    """A Travelcard period selected by the optimiser."""

    payment_type: Literal["travelcard"] = "travelcard"
    product_name: str
    zone_name: str
    max_zone: int
    start_date: date
    end_date: date
    card_cost: str
    outside_payg_cost: str
    total_cost: str
    covered_journey_count: int
    uncovered_journey_count: int


PaymentSelectionResponse = Annotated[
    PaygSelectionResponse | TravelcardSelectionResponse,
    Field(discriminator="payment_type")]


class AnalysisResponse(BaseModel):
    """Complete result returned for one FareWise analysis."""

    journey_start_date: date
    journey_end_date: date
    recorded_payg_total: str
    optimized_total: str
    estimated_saving: str
    uses_travelcard: bool
    input_summary: InputSummaryResponse | None
    selections: list[PaymentSelectionResponse]
    warnings: list[str]
