"""Access to the official monthly index series and cumulative adjustment factors.

All arithmetic is `decimal.Decimal`, never float. The engine's golden rule: a month that is
not published or ingested is an **explicit error** (`IndexUnavailableError`), never an
extrapolation or an estimate.

Period convention of the cumulative factor: `cumulative_factor(series, start, end)` multiplies
the monthly changes of the months from `start` up to the month before `end`, i.e. it adjusts a
value from the 1st day of `start` to the 1st day of `end`.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "indices" / "data"
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

HUNDRED = Decimal("100")
ONE = Decimal("1")


class IndexDataError(Exception):
    """Base class for index access and calculation input errors."""


class UnknownSeriesError(IndexDataError):
    pass


class InvalidMonthError(IndexDataError):
    pass


class IndexUnavailableError(IndexDataError):
    """A month the calculation needs has not been published or ingested yet."""


def validate_month(month: str) -> str:
    if not _MONTH_RE.match(month):
        raise InvalidMonthError(f"Invalid month: {month!r} (expected format: YYYY-MM).")
    return month


def next_month(month: str) -> str:
    year, m = int(month[:4]), int(month[5:7])
    return f"{year + (m == 12):04d}-{(m % 12) + 1:02d}"


class IndexRepository:
    """Repository of monthly series loaded from `indices/data/*.json`."""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self._cache: dict[str, dict] = {}

    def series_available(self) -> list[str]:
        return sorted(p.stem for p in self.data_dir.glob("*.json"))

    def _load(self, series: str) -> dict:
        if series not in self._cache:
            path = self.data_dir / f"{series}.json"
            if not path.exists():
                available = ", ".join(self.series_available()) or "(none)"
                raise UnknownSeriesError(
                    f"Series {series!r} not found in {self.data_dir}. Available: {available}."
                )
            self._cache[series] = json.loads(path.read_text(encoding="utf-8"))
        return self._cache[series]

    def metadata(self, series: str) -> dict:
        doc = self._load(series)
        return {key: value for key, value in doc.items() if key != "months"}

    def months(self, series: str) -> dict[str, Decimal]:
        doc = self._load(series)
        return {m: Decimal(v) for m, v in doc["months"].items()}

    def latest_month(self, series: str) -> str:
        return max(self._load(series)["months"])

    def monthly_change(self, series: str, month: str) -> Decimal:
        """Monthly change (%) of the month, or the monthly factor for series whose unit is 'factor'."""
        validate_month(month)
        doc = self._load(series)
        values = doc["months"]
        if month not in values:
            raise IndexUnavailableError(
                f"{doc['name']}: month {month} not published/ingested. "
                f"Latest available: {max(values)}. The calculation cannot proceed: "
                f"the engine never extrapolates indices."
            )
        return Decimal(values[month])

    def monthly_factor(self, series: str, month: str) -> Decimal:
        """Multiplicative factor of the month: (1 + change/100), or the value itself for factor series."""
        value = self.monthly_change(series, month)
        if self._load(series).get("unit") == "factor":
            return value
        return ONE + value / HUNDRED

    def cumulative_factor(self, series: str, start: str, end: str) -> Decimal:
        """Adjustment factor from the 1st day of `start` to the 1st day of `end`.

        Multiplies the monthly factors of the months in `[start, end)`. `start == end`
        returns 1. Any missing month in the interval raises `IndexUnavailableError`.
        """
        validate_month(start)
        validate_month(end)
        if start > end:
            raise InvalidMonthError(f"Inverted period: start={start} is after end={end}.")
        factor = ONE
        month = start
        while month < end:
            factor *= self.monthly_factor(series, month)
            month = next_month(month)
        return factor

    def adjust(self, series: str, amount: Decimal | str, start: str, end: str) -> Decimal:
        """Amount adjusted for inflation from `start` to `end` (unrounded)."""
        return Decimal(amount) * self.cumulative_factor(series, start, end)
