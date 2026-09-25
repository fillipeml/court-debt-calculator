"""Index repository and cumulative factor.

Two families: exact tests over synthetic series (arithmetic checkable by hand) and smoke tests
over the real data versioned in `indices/data`.
"""

import json
from decimal import Decimal

import pytest

from debt_engine.indices import (
    IndexRepository,
    IndexUnavailableError,
    InvalidMonthError,
    UnknownSeriesError,
)


@pytest.fixture()
def synthetic_repo(tmp_path):
    """A percentage series with 3 months and a series of monthly factors."""
    (tmp_path / "test_pct.json").write_text(
        json.dumps(
            {
                "sgs_series": 999,
                "name": "Test series (%)",
                "unit": "% per month",
                "months": {"2025-01": "1.00", "2025-02": "2.00", "2025-03": "0.50"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_factor.json").write_text(
        json.dumps(
            {
                "sgs_series": 998,
                "name": "Test series (factor)",
                "unit": "factor",
                "months": {"2025-01": "1.01", "2025-02": "1.02"},
            }
        ),
        encoding="utf-8",
    )
    return IndexRepository(tmp_path)


class TestSyntheticCumulativeFactor:
    def test_one_month(self, synthetic_repo):
        assert synthetic_repo.cumulative_factor("test_pct", "2025-01", "2025-02") == Decimal("1.01")

    def test_exact_compound_factor(self, synthetic_repo):
        # 1.01 * 1.02 * 1.005 = 1.0353651
        factor = synthetic_repo.cumulative_factor("test_pct", "2025-01", "2025-04")
        assert factor == Decimal("1.01") * Decimal("1.02") * Decimal("1.005")

    def test_empty_period_is_one(self, synthetic_repo):
        assert synthetic_repo.cumulative_factor("test_pct", "2025-02", "2025-02") == Decimal("1")

    def test_factor_series_uses_the_value_directly(self, synthetic_repo):
        factor = synthetic_repo.cumulative_factor("test_factor", "2025-01", "2025-03")
        assert factor == Decimal("1.01") * Decimal("1.02")

    def test_adjust_amount(self, synthetic_repo):
        adjusted = synthetic_repo.adjust("test_pct", "1000.00", "2025-01", "2025-02")
        assert adjusted == Decimal("1010.0000")

    def test_arithmetic_is_decimal_not_float(self, synthetic_repo):
        factor = synthetic_repo.cumulative_factor("test_pct", "2025-01", "2025-04")
        assert isinstance(factor, Decimal)


class TestGoldenRule:
    """A missing index is an explicit error. Never extrapolate."""

    def test_future_month_unavailable(self, synthetic_repo):
        with pytest.raises(IndexUnavailableError, match="2025-04"):
            synthetic_repo.cumulative_factor("test_pct", "2025-01", "2025-05")

    def test_month_before_the_series_starts(self, synthetic_repo):
        with pytest.raises(IndexUnavailableError, match="2024-12"):
            synthetic_repo.cumulative_factor("test_pct", "2024-12", "2025-02")

    def test_message_names_the_latest_available_month(self, synthetic_repo):
        with pytest.raises(IndexUnavailableError, match="Latest available: 2025-03"):
            synthetic_repo.monthly_change("test_pct", "2026-01")

    def test_unknown_series(self, synthetic_repo):
        with pytest.raises(UnknownSeriesError):
            synthetic_repo.monthly_change("does_not_exist", "2025-01")

    def test_malformed_month(self, synthetic_repo):
        with pytest.raises(InvalidMonthError):
            synthetic_repo.monthly_change("test_pct", "01/2025")

    def test_inverted_period(self, synthetic_repo):
        with pytest.raises(InvalidMonthError):
            synthetic_repo.cumulative_factor("test_pct", "2025-03", "2025-01")


class TestRealData:
    def test_essential_series_present(self, repo):
        available = repo.series_available()
        for essential in ("ipca", "inpc", "selic_monthly", "legal_rate"):
            assert essential in available

    def test_factor_equals_the_product_of_the_changes(self, repo):
        """`cumulative_factor` matches the manual product of the monthly changes."""
        values = repo.months("ipca")
        expected = Decimal("1")
        for month in ("2024-09", "2024-10", "2024-11", "2024-12"):
            expected *= Decimal("1") + values[month] / Decimal("100")
        assert repo.cumulative_factor("ipca", "2024-09", "2025-01") == expected

    def test_legal_rate_starts_with_law_14905(self, repo):
        """The Legal Rate exists since Aug/2024 (Law 14,905/2024 in force)."""
        assert min(repo.months("legal_rate")) == "2024-08"

    def test_full_year_inflation_in_a_plausible_band(self, repo):
        """Sanity: IPCA accumulated in 2025 between 0 % and 20 %."""
        factor = repo.cumulative_factor("ipca", "2025-01", "2026-01")
        assert Decimal("1.00") < factor < Decimal("1.20")

    def test_metadata_has_english_keys(self, repo):
        meta = repo.metadata("ipca")
        assert {"sgs_series", "name", "unit", "source", "captured_at"} <= set(meta)
        assert "months" not in meta
