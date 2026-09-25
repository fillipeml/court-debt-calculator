"""Interest module.

Convention validated in reference cases 01 to 04 (JuriscalcWeb): period `[start, end)`, the
first day counts and the end day does not; pro rata by calendar days over the real days of the
month; simple interest.
"""

import json
from datetime import date
from decimal import Decimal

import pytest

from debt_engine.indices import IndexRepository, IndexUnavailableError, InvalidMonthError
from debt_engine.interest import (
    fixed_monthly_pct,
    interest_amount,
    legal_interest_pct,
    legal_rate_pct,
    simple_interest_pct,
)
from tests.helpers import cents, pct6


@pytest.fixture()
def synthetic_repo(tmp_path):
    """Synthetic Legal Rate from Aug/2024 (the real start of the series)."""
    (tmp_path / "legal_rate.json").write_text(
        json.dumps(
            {
                "sgs_series": 29543,
                "name": "Legal Rate (test)",
                "unit": "% per month",
                "months": {"2024-08": "0.62", "2024-09": "0.90", "2024-10": "1.24"},
            }
        ),
        encoding="utf-8",
    )
    return IndexRepository(tmp_path)


class TestSimpleInterest:
    def test_full_months_add_without_compounding(self, synthetic_repo):
        # [01/09 -> 01/10): the whole of September = 0.90 (a plain sum, no compounding)
        pct = legal_rate_pct(synthetic_repo, date(2024, 9, 1), date(2024, 10, 1))
        assert pct == Decimal("0.90")

    def test_first_day_counts_end_day_does_not(self, synthetic_repo):
        # [09/09 -> 10/09) = 1 day (the 9th)
        pct = legal_rate_pct(synthetic_repo, date(2024, 9, 9), date(2024, 9, 10))
        assert pct == Decimal("0.90") / Decimal(30)

    def test_pro_rata_at_both_edges(self, synthetic_repo):
        # [15/09 -> 15/10): Sep 16 days (15..30) of 30 + Oct 14 days (1..14) of 31
        pct = legal_rate_pct(synthetic_repo, date(2024, 9, 15), date(2024, 10, 15))
        expected = Decimal("0.90") * Decimal(16) / Decimal(30) + Decimal("1.24") * Decimal(
            14
        ) / Decimal(31)
        assert pct == expected

    def test_empty_period_is_zero(self, synthetic_repo):
        assert legal_rate_pct(synthetic_repo, date(2024, 9, 10), date(2024, 9, 10)) == 0

    def test_month_without_a_published_rate_is_an_error(self, synthetic_repo):
        with pytest.raises(IndexUnavailableError, match="2024-11"):
            legal_rate_pct(synthetic_repo, date(2024, 10, 15), date(2024, 11, 10))

    def test_inverted_period(self, synthetic_repo):
        with pytest.raises(InvalidMonthError):
            legal_rate_pct(synthetic_repo, date(2024, 10, 10), date(2024, 10, 1))

    def test_iso_string_dates(self, synthetic_repo):
        pct = legal_rate_pct(synthetic_repo, "2024-09-01", "2024-10-01")
        assert pct == Decimal("0.90")

    def test_generic_rate_per_day(self):
        pct = simple_interest_pct(lambda _d: Decimal("1.5"), date(2025, 1, 1), date(2025, 2, 1))
        assert pct == Decimal("1.5")


class TestLegalInterestTimeline:
    def test_regime_switch_on_30_08_2024(self, synthetic_repo):
        # [15/08/2024 -> 10/09/2024): 1 % for 15 days of Aug (15..29) +
        # LR Aug (0.62) for 2 days (30..31) + LR Sep (0.90) for 9 days (1..9)
        pct = legal_interest_pct(synthetic_repo, date(2024, 8, 15), date(2024, 9, 10))
        expected = (
            Decimal("1.0") * Decimal(15) / Decimal(31)
            + Decimal("0.62") * Decimal(2) / Decimal(31)
            + Decimal("0.90") * Decimal(9) / Decimal(30)
        )
        assert pct == expected

    def test_pure_1_pct_regime_does_not_read_any_series(self, tmp_path):
        # the whole period under 1 %: no legal_rate needed in the repository
        empty_repo = IndexRepository(tmp_path)
        pct = legal_interest_pct(empty_repo, date(2020, 1, 1), date(2020, 3, 1))
        assert pct == Decimal("2.0")

    def test_switch_from_0_5_to_1_pct_on_11_01_2003(self, tmp_path):
        # [01/01/2003 -> 01/02/2003): 0.5 % for 10 days (1..10) + 1 % for 21 days (11..31)
        empty_repo = IndexRepository(tmp_path)
        pct = legal_interest_pct(empty_repo, date(2003, 1, 1), date(2003, 2, 1))
        expected = Decimal("0.5") * Decimal(10) / Decimal(31) + Decimal("1.0") * Decimal(
            21
        ) / Decimal(31)
        assert pct == expected


class TestFixedMonthlyRate:
    def test_inclusive_calendar_months(self):
        # Dec/2024, Jan/2025, Feb/2025 = 3 months
        assert fixed_monthly_pct("1.0", date(2024, 12, 31), date(2025, 2, 1)) == Decimal("3.0")

    def test_same_month_counts_one(self):
        assert fixed_monthly_pct("1.0", date(2025, 3, 5), date(2025, 3, 20)) == Decimal("1.0")

    def test_case_02_75_months(self):
        pct = fixed_monthly_pct("1.0", date(2020, 3, 15), date(2026, 5, 22))
        assert pct == Decimal("75.0")


class TestReferenceCase01InterestLine:
    """Interest line of case 01: Legal Rate from 15/05/2026 to 22/05/2026 = 7 days."""

    def test_legal_rate_pct(self, repo):
        pct = legal_rate_pct(repo, date(2026, 5, 15), date(2026, 5, 22))
        assert pct6(pct) == Decimal("0.044776")

    def test_interest_amount_over_the_adjusted_amount(self, repo):
        pct = legal_interest_pct(repo, date(2026, 5, 15), date(2026, 5, 22))
        assert cents(interest_amount(Decimal("162290.65"), pct)) == Decimal("72.67")
