"""Deductions (contractual penalty + fixed) and awarded fees.

They model the structure of a real-estate rescission judgment: refund minus a 25 % penalty,
minus assessed deductions (usage fee, condominium charges), with awarded fees over the updated
claim value. Arithmetic checkable by hand; goldens 01 to 05 guarantee nothing regressed when
there are no deductions.
"""

from datetime import date
from decimal import Decimal

import pytest

from debt_engine.calculation import (
    CalculationInputError,
    CalculationParameters,
    Deduction,
    Installment,
    calculate,
)

BASE = dict(final_date=date(2026, 5, 22), adjust_until="2026-04")


@pytest.fixture(scope="module")
def case_with_deductions(repo):
    """Case 01 (A = 162,363.32) + 25 % penalty over the gross + 2 fixed deductions + 5 %
    awarded fees over the net + art. 523 at 10 %."""
    return calculate(
        repo,
        [Installment(Decimal("134000.00"), date(2022, 3, 2))],
        CalculationParameters(
            **BASE,
            interest_start=date(2026, 5, 15),
            penalty_pct=Decimal("25"),
            penalty_base="gross",
            deductions=(
                Deduction("Assessed usage fee", Decimal("1399.75")),
                Deduction("Outstanding condominium charges", Decimal("1097.66")),
            ),
            awarded_fee_pct=Decimal("5"),
            awarded_fee_base="net",
            fine_523_pct=Decimal("10"),
            fee_523_pct=Decimal("10"),
        ),
    )


class TestDeductions:
    def test_penalty_25_pct_over_gross(self, case_with_deductions):
        # A = 162,363.32 -> 25 % = 40,590.83
        assert case_with_deductions.penalty == Decimal("40590.83")

    def test_fixed_deductions_added(self, case_with_deductions):
        assert case_with_deductions.total_fixed_deductions == Decimal("2497.41")

    def test_net_is_a_minus_deductions(self, case_with_deductions):
        # 162,363.32 - 40,590.83 - 2,497.41 = 119,275.08
        assert case_with_deductions.net_amount == Decimal("119275.08")

    def test_awarded_fees_over_the_net(self, case_with_deductions):
        # 5 % of 119,275.08 = 5,963.75 (half-up of 5,963.754)
        assert case_with_deductions.awarded_fees == Decimal("5963.75")

    def test_523_accrues_on_the_enforceable_amount(self, case_with_deductions):
        # enforceable = 119,275.08 + 5,963.75 = 125,238.83 -> 10 % = 12,523.88
        assert case_with_deductions.enforceable_amount == Decimal("125238.83")
        assert case_with_deductions.fine_523 == Decimal("12523.88")
        assert case_with_deductions.fee_523 == Decimal("12523.88")

    def test_self_consistent_totals(self, case_with_deductions):
        r = case_with_deductions
        assert r.creditor_amount == r.net_amount + r.fine_523
        assert r.grand_total == r.enforceable_amount + r.fine_523 + r.fee_523
        assert r.grand_total == Decimal("150286.59")

    def test_as_dict_carries_the_new_fields(self, case_with_deductions):
        d = case_with_deductions.as_dict()
        assert d["totals"]["penalty"] == "40590.83"
        assert d["totals"]["net_amount"] == "119275.08"
        assert len(d["deductions"]) == 2


@pytest.fixture(scope="module")
def installments():
    return [Installment(Decimal("10000.00"), date(2024, 10, 10))]


class TestPenaltyBases:
    def test_nominal_base(self, repo, installments):
        r = calculate(
            repo,
            installments,
            CalculationParameters(
                **BASE, interest_regime="none", penalty_pct=Decimal("25"), penalty_base="nominal"
            ),
        )
        assert r.penalty == Decimal("2500.00")

    def test_adjusted_base(self, repo, installments):
        r = calculate(
            repo,
            installments,
            CalculationParameters(
                **BASE, interest_regime="none", penalty_pct=Decimal("25"), penalty_base="adjusted"
            ),
        )
        assert r.penalty == (r.total_adjusted * Decimal("0.25")).quantize(Decimal("0.01"))

    def test_invalid_base_is_an_error(self, repo, installments):
        with pytest.raises(CalculationInputError, match="penalty base"):
            calculate(
                repo,
                installments,
                CalculationParameters(**BASE, penalty_pct=Decimal("25"), penalty_base="ceiling"),
            )


class TestAwardedFees:
    def test_over_the_nominal_claim_value(self, repo):
        r = calculate(
            repo,
            [Installment(Decimal("1000.00"), date(2025, 1, 10))],
            CalculationParameters(
                **BASE,
                interest_regime="none",
                awarded_fee_pct=Decimal("10"),
                awarded_fee_base="claim_value",
                claim_value=Decimal("48990.00"),
            ),
        )
        assert r.awarded_fees == Decimal("4899.00")
        assert r.adjusted_claim_value is None

    def test_over_the_adjusted_claim_value(self, repo):
        r = calculate(
            repo,
            [Installment(Decimal("1000.00"), date(2025, 1, 10))],
            CalculationParameters(
                **BASE,
                interest_regime="none",
                awarded_fee_pct=Decimal("10"),
                awarded_fee_base="claim_value",
                claim_value=Decimal("48990.00"),
                claim_value_month="2025-06",
            ),
        )
        factor = r.adjusted_claim_value / Decimal("48990.00")
        assert factor > 1  # there was an adjustment
        assert r.awarded_fees == (r.adjusted_claim_value * Decimal("0.10")).quantize(
            Decimal("0.01")
        )

    def test_missing_claim_value_is_an_error(self, repo):
        with pytest.raises(CalculationInputError, match="claim_value"):
            calculate(
                repo,
                [Installment(Decimal("1000.00"), date(2025, 1, 10))],
                CalculationParameters(
                    **BASE, awarded_fee_pct=Decimal("10"), awarded_fee_base="claim_value"
                ),
            )

    def test_invalid_fee_base_is_an_error(self, repo):
        with pytest.raises(CalculationInputError, match="fee base"):
            calculate(
                repo,
                [Installment(Decimal("1000.00"), date(2025, 1, 10))],
                CalculationParameters(
                    **BASE, awarded_fee_pct=Decimal("10"), awarded_fee_base="gross"
                ),
            )


class TestRegressionWithoutDeductions:
    def test_without_deductions_the_enforceable_amount_equals_a(self, repo):
        """Guarantees goldens 01 to 05 remain valid: without penalty, deductions and awarded
        fees, the base of art. 523 is still (A)."""
        r = calculate(
            repo,
            [Installment(Decimal("134000.00"), date(2022, 3, 2))],
            CalculationParameters(
                **BASE,
                interest_start=date(2026, 5, 15),
                fine_523_pct=Decimal("10"),
                fee_523_pct=Decimal("10"),
            ),
        )
        assert r.net_amount == r.gross_total == Decimal("162363.32")
        assert r.enforceable_amount == Decimal("162363.32")
        assert r.fine_523 == Decimal("16236.33")
        assert r.grand_total == Decimal("194835.98")
