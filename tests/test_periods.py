"""Tests for travel period construction and date calculations."""

from datetime import date

import pytest

from src.periods import (DatePeriod,
                         PeriodKind,
                         build_period,
                         monthly_end_date,
                         start_dates)


def test_date_period_contains_start_end_and_middle_dates() -> None:
    """Verify that date period contains start end and middle dates."""
    period = DatePeriod(kind=PeriodKind.SEVEN_DAY,
                        start_date=date(2026, 3, 1),
                        end_date=date(2026, 3, 7))
    assert period.contains(date(2026, 3, 1))
    assert period.contains(date(2026, 3, 4))
    assert period.contains(date(2026, 3, 7))
    assert not period.contains(date(2026, 2, 28))
    assert not period.contains(date(2026, 3, 8))


def test_date_period_day_count_is_inclusive() -> None:
    """Verify that date period day count is inclusive."""
    period = DatePeriod(kind=PeriodKind.SEVEN_DAY,
                        start_date=date(2026, 3, 1),
                        end_date=date(2026, 3, 7))
    assert period.day_count == 7


@pytest.mark.parametrize(
    ("start_date", "expected"),
    [(date(2026, 1, 1), date(2026, 1, 31)),
     (date(2026, 1, 15), date(2026, 2, 14)),
     (date(2026, 1, 31), date(2026, 2, 28)),
     (date(2024, 1, 31), date(2024, 2, 29)),
     (date(2026, 12, 15), date(2027, 1, 14))])
def test_monthly_end_date_handles_calendar_boundaries(
    start_date: date,
    expected: date,
    ) -> None:
    """Verify that monthly end date handles calendar boundaries."""
    assert monthly_end_date(start_date) == expected


@pytest.mark.parametrize(
    ("kind", "expected_end"),
    [(PeriodKind.ONE_DAY, date(2026, 3, 1)),
     (PeriodKind.SEVEN_DAY, date(2026, 3, 7)),
     (PeriodKind.MONTHLY, date(2026, 3, 31))])
def test_build_period_builds_expected_date_range(
    kind: PeriodKind,
    expected_end: date,
    ) -> None:
    """Verify that build period builds expected date range."""
    period = build_period(date(2026, 3, 1), kind)
    assert period == DatePeriod(kind=kind,
                                start_date=date(2026, 3, 1),
                                end_date=expected_end)


def test_build_period_rejects_unsupported_kind() -> None:
    """Verify that build period rejects unsupported kind."""
    with pytest.raises(ValueError, match="Unsupported period kind"):
        build_period(date(2026, 3, 1), "unsupported")  # type: ignore[arg-type]


def test_start_dates_returns_inclusive_date_sequence() -> None:
    """Verify that start dates returns inclusive date sequence."""
    assert start_dates(date(2026, 3, 1), date(2026, 3, 3)) == [
        date(2026, 3, 1),
        date(2026, 3, 2),
        date(2026, 3, 3)]


def test_start_dates_returns_empty_list_for_reversed_range() -> None:
    """Verify that start dates returns empty list for reversed range."""
    assert start_dates(date(2026, 3, 2), date(2026, 3, 1)) == []
