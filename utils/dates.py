from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import calendar
from typing import Optional, Tuple


@dataclass(frozen=True)
class DateRange:
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD


def _parse_ymd(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def normalize_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
) -> DateRange:
    """
    Normalize date range for tools:
    - If end_date is missing -> today
    - If start_date is missing -> first day of end_date's month
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    end_dt = _parse_ymd(end_date)

    if start_date is None:
        start_dt = end_dt.replace(day=1)
        start_date = start_dt.strftime("%Y-%m-%d")
    else:
        _parse_ymd(start_date)  # validate

    return DateRange(start_date=start_date, end_date=end_date)


def month_start_end(month_ym: str) -> Tuple[str, str]:
    """month_ym: 'YYYY-MM' -> ('YYYY-MM-01', 'YYYY-MM-lastday')"""
    year, month = map(int, month_ym.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return (f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}")


def add_months(year: int, month: int, delta: int) -> Tuple[int, int]:
    """Add delta months to (year, month) returning normalized (year, month)."""
    total = (year * 12 + (month - 1)) + delta
    new_year = total // 12
    new_month = (total % 12) + 1
    return new_year, new_month
