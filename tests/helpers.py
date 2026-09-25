"""Helpers shared by the engine and API test suites."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from debt_engine.indices import IndexRepository

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "indices" / "data"


def cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def pct6(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def adjust_tjdft(repo: IndexRepository, amount: str, first_month: str) -> Decimal:
    """'Official TJDFT indices' adjustment: INPC up to 08/2024 + IPCA from 09/2024, up to the
    month 04/2026 (the latest published on the date of the reference calculations)."""
    factor = repo.cumulative_factor("inpc", first_month, "2024-09") * repo.cumulative_factor(
        "ipca", "2024-09", "2026-05"
    )
    return Decimal(amount) * factor
