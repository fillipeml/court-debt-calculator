"""Deterministic engine for updating court-ordered debts in Brazil.

The model interprets, the engine computes. A language model never does the arithmetic:
everything here is `decimal.Decimal` over official monthly indices versioned in git, and a
missing index month is an explicit error, never an estimate.
"""

from debt_engine.indices import (
    IndexDataError,
    IndexRepository,
    IndexUnavailableError,
    InvalidMonthError,
    UnknownSeriesError,
)
from debt_engine.interest import (
    fixed_monthly_pct,
    interest_amount,
    legal_interest_pct,
    legal_rate_pct,
    simple_interest_pct,
)

__version__ = "0.1.0"

__all__ = [
    "IndexRepository",
    "IndexDataError",
    "IndexUnavailableError",
    "UnknownSeriesError",
    "InvalidMonthError",
    "simple_interest_pct",
    "legal_interest_pct",
    "legal_rate_pct",
    "fixed_monthly_pct",
    "interest_amount",
    "__version__",
]
