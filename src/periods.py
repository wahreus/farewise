import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

class PeriodKind(str, Enum):
    ONE_DAY = "one_day"
    SEVEN_DAY = "seven_day"
    MONTHLY = "monthly"

@dataclass(frozen=True)
class DatePeriod:
    kind: PeriodKind
    start_date: date
    end_date: date

    def contains(self, value: date) -> bool:
        return self.start_date <= value <= self.end_date

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1

def monthly_end_date(start_date: date) -> date:
    if start_date.month == 12:
        next_year = start_date.year + 1
        next_month = 1
    else:
        next_year = start_date.year
        next_month = start_date.month + 1
    days_in_next_month = calendar.monthrange(next_year, next_month)[1]
    if start_date.day > days_in_next_month:
        return date(next_year, next_month, days_in_next_month)
    same_day_next_month = date(next_year, next_month, start_date.day)
    return same_day_next_month - timedelta(days=1)

def build_period(start_date: date, kind: PeriodKind) -> DatePeriod:
    if kind == PeriodKind.ONE_DAY:
        end_date = start_date
    elif kind == PeriodKind.SEVEN_DAY:
        end_date = start_date + timedelta(days=6)
    elif kind == PeriodKind.MONTHLY:
        end_date = monthly_end_date(start_date)
    else:
        raise ValueError(f"Unsupported period kind: {kind}")
    return DatePeriod(kind=kind,
                      start_date=start_date,
                      end_date=end_date)

def start_dates(first_date: date, last_date: date) -> list[date]:
    if last_date < first_date:
        return []
    day_count = (last_date - first_date).days + 1
    return [first_date + timedelta(days=offset)
            for offset in range(day_count)]
