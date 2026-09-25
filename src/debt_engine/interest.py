"""Default interest: the legal-interest timeline, the Legal Rate and fixed monthly rates.

Legal grounds and validation:

* **CMN Resolution 5,171/2024**: art. 6, simple interest in the monthly accumulation and in
  the pro-rata (rate of the month / calendar days of the month x days accrued); art. 7,
  interest accrues on the amount **already adjusted** for inflation.
* **Reference cases 01 to 05** (docs/REFERENCE_CASES.md): conventions validated to the cent
  against the TJDFT's public calculator (JuriscalcWeb).

Conventions (JuriscalcWeb, confirmed by cases 01/03/04):

* Interest period `[start, end)`: **the first day counts, the end day does not**. Example:
  15/05 to 22/05 = 7 days (15..21).
* **Legal interest** (Civil Code art. 406): 0.5 % per month until 10/01/2003; 1 % per month
  from 11/01/2003 to 29/08/2024; the **Legal Rate** (central bank series 29543) from
  30/08/2024. Pro rata by calendar days over the real days of the month at every edge,
  including the regime switch (Aug/2024: 29/31 at 1 % plus 2/31 of the Legal Rate).
* **Fixed rate** (JuriscalcWeb's own regime): counts **inclusive calendar months** of the two
  edge months, no pro rata (case 02: Mar/2020 to May/2026 = 75 months).

Precision note: JuriscalcWeb computes in float64 (JavaScript), which makes the 6th decimal of
the displayed percentage oscillate by ±0.000001 between scenarios. This engine uses exact
`Decimal`; the guaranteed parity is **to the cent** in money, and ±0.000001 in the displayed
percentage.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from debt_engine.indices import IndexRepository, InvalidMonthError

HUNDRED = Decimal("100")

LEGAL_RATE_SERIES = "legal_rate"
LEGAL_RATE_START = date(2024, 8, 30)  # Law 14,905/2024 (CMN Res. 5,171, art. 8, sole paragraph)
ONE_PCT_START = date(2003, 1, 11)  # Civil Code 2002, art. 406 with National Tax Code art. 161 §1
RATE_ONE_PCT = Decimal("1.0")
RATE_HALF_PCT = Decimal("0.5")  # Civil Code 1916, art. 1,062


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + (month == 12), (month % 12) + 1)


def _to_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidMonthError(f"Invalid date: {value!r} (expected format: YYYY-MM-DD).") from None


def simple_interest_pct(
    rate_of_day: Callable[[date], Decimal], start: date | str, end: date | str
) -> Decimal:
    """Accumulated simple-interest percentage in the period `[start, end)`.

    Groups the accrued days of each month by the rate in force and sums
    `rate x days / days_in_month` per group (simple interest: a sum, never compounding,
    CMN Res. 5,171/2024, art. 6).
    """
    start, end = _to_date(start), _to_date(end)
    if end < start:
        raise InvalidMonthError(f"Inverted period: start={start} is after end={end}.")

    total = Decimal("0")
    year, month = start.year, start.month
    while date(year, month, 1) < end:
        days_in_month = _days_in_month(year, month)
        groups: dict[Decimal, int] = {}
        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            if start <= d < end:
                rate = rate_of_day(d)
                groups[rate] = groups.get(rate, 0) + 1
        for rate, days in groups.items():
            total += rate * Decimal(days) / Decimal(days_in_month)
        year, month = _next_month(year, month)
    return total


def _legal_rate_of_day(repo: IndexRepository, d: date) -> Decimal:
    return repo.monthly_change(LEGAL_RATE_SERIES, f"{d.year:04d}-{d.month:02d}")


def legal_interest_pct(repo: IndexRepository, start: date | str, end: date | str) -> Decimal:
    """Legal interest of Civil Code art. 406 in `[start, end)`: the timeline
    0.5 % -> 1 % (11/01/2003) -> Legal Rate (30/08/2024), pro rata die.

    A Legal Rate month that is not published raises `IndexUnavailableError`.
    """

    def rate(d: date) -> Decimal:
        if d >= LEGAL_RATE_START:
            return _legal_rate_of_day(repo, d)
        if d >= ONE_PCT_START:
            return RATE_ONE_PCT
        return RATE_HALF_PCT

    return simple_interest_pct(rate, start, end)


def legal_rate_pct(repo: IndexRepository, start: date | str, end: date | str) -> Decimal:
    """The Legal Rate only (series 29543) in `[start, end)`, pro rata die."""
    return simple_interest_pct(lambda d: _legal_rate_of_day(repo, d), start, end)


def fixed_monthly_pct(
    monthly_rate_pct: Decimal | str, start: date | str, end: date | str
) -> Decimal:
    """Fixed percentage by inclusive calendar months (JuriscalcWeb's "fixed percentage"
    regime): both edge months count in full.

    Case 02: 15/03/2020 -> 22/05/2026 = 75 months x 1 % = 75 %.
    """
    start, end = _to_date(start), _to_date(end)
    if end < start:
        raise InvalidMonthError(f"Inverted period: start={start} is after end={end}.")
    months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    return Decimal(monthly_rate_pct) * Decimal(months)


def interest_amount(adjusted_amount: Decimal | str, accumulated_pct: Decimal) -> Decimal:
    """Interest on the adjusted amount (CMN Res. 5,171/2024, art. 7)."""
    return Decimal(adjusted_amount) * accumulated_pct / HUNDRED
