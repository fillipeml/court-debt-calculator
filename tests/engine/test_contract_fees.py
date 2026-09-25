"""CONTRACT fees (client x law firm): an INFORMATIVE line of the statement.

Rules:

* % over the CREDITOR'S AMOUNT (what the client actually receives);
* never part of the debtor's debt: no total of the calculation changes;
* checkable from the displayed values (CPC art. 524, I):
  withheld = pct x creditor's amount; net = creditor's amount - withheld.

There is no external benchmark (JuriscalcWeb and Dr. Calc have no concept of an informative
withholding): validation by internal consistency.
"""

from datetime import date
from decimal import Decimal

from debt_engine.calculation import CalculationParameters, Installment, calculate

INSTALLMENT = [Installment(Decimal("25000.00"), date(2024, 5, 10), "Award")]


def _params(**kw):
    return CalculationParameters(
        final_date=date(2026, 7, 31),
        adjust_until="2026-06",
        index="tjdft",
        interest_start=date(2025, 1, 10),
        awarded_fee_pct=Decimal("10"),
        fine_523_pct=Decimal("10"),
        **kw,
    )


class TestContractFees:
    def test_withheld_and_net_are_checkable(self, repo):
        r = calculate(repo, INSTALLMENT, _params(contract_fee_pct=Decimal("20")))
        expected = (r.creditor_amount * Decimal("20") / 100).quantize(Decimal("0.01"))
        assert r.contract_fees == expected
        assert r.creditor_after_contract_fees == r.creditor_amount - r.contract_fees

    def test_informative_changes_no_total(self, repo):
        without = calculate(repo, INSTALLMENT, _params())
        with_fees = calculate(repo, INSTALLMENT, _params(contract_fee_pct=Decimal("20")))
        assert with_fees.grand_total == without.grand_total
        assert with_fees.enforceable_amount == without.enforceable_amount
        assert with_fees.creditor_amount == without.creditor_amount
        assert with_fees.fine_523 == without.fine_523

    def test_dict_exposes_or_omits(self, repo):
        with_fees = calculate(repo, INSTALLMENT, _params(contract_fee_pct=Decimal("20")))
        t = with_fees.as_dict()["totals"]
        assert t["contract_fees"] is not None
        assert Decimal(t["creditor_after_contract_fees"]) == Decimal(
            t["creditor_amount"]
        ) - Decimal(t["contract_fees"])
        without = calculate(repo, INSTALLMENT, _params()).as_dict()
        assert without["totals"]["contract_fees"] is None
        assert without["totals"]["creditor_after_contract_fees"] is None
        assert without["parameters"]["contract_fee_pct"] is None
