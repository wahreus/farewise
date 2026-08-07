"""Formatting and output helpers for FareWise results."""

from datetime import date
from src.fares import format_money
from src.results import OptimizationResult, PaygSelection, TravelcardSelection

def format_date(value: date) -> str:
    """Format a date for FareWise report output."""
    return value.strftime("%d %b %Y")

def format_date_range(start_date: date, end_date: date) -> str:
    """Format one date or an inclusive date range."""
    if start_date == end_date:
        return format_date(start_date)
    return f"{format_date(start_date)} - {format_date(end_date)}"

def format_payg(selection: PaygSelection) -> str:
    """Format one PAYG selection for the report."""
    period = format_date_range(selection.start_date, selection.end_date)
    journey_word = "journey" if selection.journey_count == 1 else "journeys"
    return (f"PAYG, {period}: {format_money(selection.total_cost)} "
            f"({selection.journey_count} {journey_word})")

def format_travelcard(selection: TravelcardSelection) -> str:
    """Format one Travelcard selection for the report."""
    period = format_date_range(selection.start_date, selection.end_date)
    cost_parts = f"card {format_money(selection.card_cost)}"
    if selection.outside_payg_cost:
        cost_parts += (" + outside PAYG "
                       f"{format_money(selection.outside_payg_cost)}")
    return (f"{selection.product_name} {selection.zone_name}, {period}: "
            f"{format_money(selection.total_cost)} ({cost_parts}; "
            f"{selection.covered_journey_count} covered, "
            f"{selection.uncovered_journey_count} outside)")

def format_report(result: OptimizationResult) -> str:
    """Build the complete human-readable FareWise report."""
    lines = [
        "\nFareWise result",
        "===============",
        ("Journey period: "
         f"{format_date_range(result.journey_start_date, result.journey_end_date)}"),
        f"Recorded PAYG total: {format_money(result.payg_total)}",
        f"Lowest estimated total: {format_money(result.optimized_total)}",
        f"Estimated saving: {format_money(result.savings)}",
        "",
        "Recommended strategy",
        "--------------------"]
    for selection in result.selections:
        if isinstance(selection, PaygSelection):
            lines.append(f"- {format_payg(selection)}")
        else:
            lines.append(f"- {format_travelcard(selection)}")
    if result.warnings:
        lines.extend(["", "Important limitations", "---------------------"])
        lines.extend(f"- {warning}" for warning in result.warnings)
    return "\n".join(lines) + "\n"

def print_report(result: OptimizationResult) -> None:
    """Print a formatted FareWise optimization report."""
    print(format_report(result))
