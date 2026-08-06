from datetime import date
from decimal import Decimal

from src.report import (format_date,
                        format_date_range,
                        format_payg,
                        format_report,
                        format_travelcard,
                        print_report)
from src.results import (OptimizationResult,
                         PaygSelection,
                         TravelcardSelection)


def payg_selection(journey_count: int = 2) -> PaygSelection:
    return PaygSelection(start_date=date(2026, 3, 1),
                         end_date=date(2026, 3, 2),
                         cost=Decimal("11.20"),
                         journey_count=journey_count)


def travelcard_selection(outside_payg_cost: str = "2.80",
                         ) -> TravelcardSelection:
    return TravelcardSelection(product_name="7 Day",
                               zone_name="Zones 1-2",
                               max_zone=2,
                               start_date=date(2026, 3, 3),
                               end_date=date(2026, 3, 9),
                               card_cost=Decimal("44.70"),
                               outside_payg_cost=Decimal(outside_payg_cost),
                               covered_journey_count=10,
                               uncovered_journey_count=1)


def optimization_result(warnings: tuple[str, ...] = ("Example warning",),
                        ) -> OptimizationResult:
    return OptimizationResult(
        journey_start_date=date(2026, 3, 1),
        journey_end_date=date(2026, 3, 9),
        payg_total=Decimal("60.00"),
        optimized_total=Decimal("58.70"),
        selections=(payg_selection(), travelcard_selection()),
        warnings=warnings)


def test_format_date_uses_day_abbreviated_month_and_year() -> None:
    assert format_date(date(2026, 3, 1)) == "01 Mar 2026"


def test_format_date_range_formats_single_date() -> None:
    assert format_date_range(date(2026, 3, 1),
                             date(2026, 3, 1)) == "01 Mar 2026"


def test_format_date_range_formats_multiple_dates() -> None:
    assert format_date_range(date(2026, 3, 1), date(2026, 3, 7)) == (
        "01 Mar 2026 - 07 Mar 2026")


def test_format_payg_formats_plural_journey_count() -> None:
    assert format_payg(payg_selection()) == (
        "PAYG, 01 Mar 2026 - 02 Mar 2026: £11.20 (2 journeys)")


def test_format_payg_formats_singular_journey_count() -> None:
    selection = PaygSelection(start_date=date(2026, 3, 1),
                              end_date=date(2026, 3, 1),
                              cost=Decimal("2.80"),
                              journey_count=1)
    assert format_payg(selection) == (
        "PAYG, 01 Mar 2026: £2.80 (1 journey)")


def test_format_travelcard_includes_outside_payg_cost() -> None:
    assert format_travelcard(travelcard_selection()) == (
        "7 Day Zones 1-2, 03 Mar 2026 - 09 Mar 2026: £47.50 "
        "(card £44.70 + outside PAYG £2.80; 10 covered, 1 outside)")


def test_format_travelcard_omits_zero_outside_payg_cost() -> None:
    selection = travelcard_selection(outside_payg_cost="0.00")
    assert format_travelcard(selection) == (
        "7 Day Zones 1-2, 03 Mar 2026 - 09 Mar 2026: £44.70 "
        "(card £44.70; 10 covered, 1 outside)")


def test_format_report_builds_complete_report() -> None:
    report = format_report(optimization_result())
    assert report == (
        "\nFareWise result\n"
        "===============\n"
        "Journey period: 01 Mar 2026 - 09 Mar 2026\n"
        "Recorded PAYG total: £60.00\n"
        "Lowest estimated total: £58.70\n"
        "Estimated saving: £1.30\n"
        "\n"
        "Recommended strategy\n"
        "--------------------\n"
        "- PAYG, 01 Mar 2026 - 02 Mar 2026: £11.20 (2 journeys)\n"
        "- 7 Day Zones 1-2, 03 Mar 2026 - 09 Mar 2026: £47.50 "
        "(card £44.70 + outside PAYG £2.80; 10 covered, 1 outside)\n"
        "\n"
        "Important limitations\n"
        "---------------------\n"
        "- Example warning\n")


def test_format_report_omits_limitations_without_warnings() -> None:
    report = format_report(optimization_result(warnings=()))
    assert "Important limitations" not in report
    assert report.endswith("1 outside)\n")


def test_print_report_prints_formatted_report(capsys) -> None:
    result = optimization_result(warnings=())
    print_report(result)
    assert capsys.readouterr().out == format_report(result) + "\n"
