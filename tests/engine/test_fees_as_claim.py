"""Golden: reference case 13, awarded fees as THE CLAIM being enforced.

Modelled after a real enforcement petition of case 01: the enforcement collects ONLY the
awarded attorney fees: 10 % over the economic benefit of R$ 134,000.00 updated (filed on
02/03/2022, INPC -> IPCA, Legal Rate from the final judgment on 15/05/2026) =
**R$ 16,236.33** (the literal amount of the petition's first request). The fine and the fees
of art. 523 accrue "on the total amount of the debt" = the 16,236.33.
"""

from datetime import date
from decimal import Decimal

import pytest

from debt_engine.calculation import (
    CalculationInputError,
    CalculationParameters,
    Installment,
    calculate,
)


@pytest.fixture(scope="module")
def result(repo):
    return calculate(
        repo,
        [Installment(Decimal("134000.00"), date(2022, 3, 2), "Economic benefit (base)")],
        CalculationParameters(
            final_date=date(2026, 5, 22),
            adjust_until="2026-04",
            index="tjdft",
            interest_regime="legal",
            interest_start=date(2026, 5, 15),
            awarded_fee_pct=Decimal("10"),
            awarded_fee_base="net",
            awarded_fees_are_the_claim=True,
            fine_523_pct=Decimal("10"),
            fee_523_pct=Decimal("10"),
        ),
    )


class TestCase13FeesAsTheClaim:
    def test_updated_base_a(self, result):
        # the base (updated benefit) is still demonstrated: 162,363.32
        assert result.gross_total == Decimal("162363.32")

    def test_enforced_fees_are_the_petition_amount(self, result):
        assert result.awarded_fees == Decimal("16236.33")

    def test_enforceable_amount_is_the_fees_only(self, result):
        assert result.enforceable_amount == Decimal("16236.33")

    def test_523_accrues_on_the_fees(self, result):
        assert result.fine_523 == Decimal("1623.63")
        assert result.fee_523 == Decimal("1623.63")

    def test_creditor_amount_and_total(self, result):
        assert result.creditor_amount == Decimal("17859.96")
        assert result.grand_total == Decimal("19483.59")

    def test_dict_carries_the_flag(self, result):
        d = result.as_dict()
        assert d["parameters"]["awarded_fees_are_the_claim"] is True
        assert d["totals"]["enforceable_amount"] == "16236.33"

    def test_flag_without_a_percentage_is_an_explicit_error(self, repo):
        with pytest.raises(CalculationInputError, match="percentage"):
            calculate(
                repo,
                [Installment(Decimal("1000.00"), date(2024, 1, 1))],
                CalculationParameters(
                    final_date=date(2026, 5, 22),
                    adjust_until="2026-04",
                    interest_regime="none",
                    awarded_fees_are_the_claim=True,
                ),
            )

    def test_without_the_flag_nothing_changes(self, repo):
        """Regression: with the flag off, the enforceable amount is net + fees."""
        r = calculate(
            repo,
            [Installment(Decimal("134000.00"), date(2022, 3, 2))],
            CalculationParameters(
                final_date=date(2026, 5, 22),
                adjust_until="2026-04",
                index="tjdft",
                interest_regime="legal",
                interest_start=date(2026, 5, 15),
                awarded_fee_pct=Decimal("10"),
            ),
        )
        assert r.enforceable_amount == Decimal("162363.32") + Decimal("16236.33")
