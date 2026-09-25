"""Fees provided for in the TITLE itself: the second component that ADDS to the debt.

Motivating case: a debt acknowledgement with a clause reading "a 10 % fine, default interest
of 1 % per month and monetary adjustment, as well as (...) attorney fees of 20 % over the
total amount of the debt, to which the DEBTOR hereby consents". Fees provided for in the title
with express consent ARE PART of the debt, next to the awarded fees.

Rules (internal consistency, no external benchmark; enforceability is a legal decision of
whoever calculates):
* base = net refund; the late fine enters the base only with title_fee_on_fine=True ("over
  the total amount of the debt");
* adds to the enforceable amount (art. 523 accrues as a consequence);
* out of the creditor's amount (fees belong to the lawyer);
* without the field, nothing changes (regression).
"""

from datetime import date
from decimal import Decimal

from debt_engine.calculation import CalculationParameters, Installment, calculate

INSTALLMENTS = [
    Installment(Decimal("29000.00"), date(2019, 9, 26), "Down payment"),
    Installment(Decimal("7800.00"), date(2019, 10, 26), "Installment 1 of 10"),
]


def _params(**kw):
    return CalculationParameters(
        final_date=date(2026, 7, 31),
        adjust_until="2026-06",
        index="inpc",
        interest_regime="fixed",
        fixed_monthly_rate=Decimal("1.00"),
        late_fine_pct=Decimal("10"),
        **kw,
    )


class TestTitleFees:
    def test_base_without_the_fine_by_default(self, repo):
        r = calculate(repo, INSTALLMENTS, _params(title_fee_pct=Decimal("20")))
        assert r.title_fee_base == r.net_amount - r.total_late_fine
        expected = (r.title_fee_base * 20 / 100).quantize(Decimal("0.01"))
        assert r.title_fees == expected

    def test_over_the_total_amount_of_the_debt(self, repo):
        """The clause: '20 % over the total amount of the debt', the fine in the base."""
        r = calculate(
            repo, INSTALLMENTS, _params(title_fee_pct=Decimal("20"), title_fee_on_fine=True)
        )
        assert r.title_fee_base == r.net_amount

    def test_adds_to_the_enforceable_amount_and_stays_out_of_the_creditor(self, repo):
        without = calculate(repo, INSTALLMENTS, _params())
        with_fees = calculate(repo, INSTALLMENTS, _params(title_fee_pct=Decimal("20")))
        assert with_fees.enforceable_amount == without.enforceable_amount + with_fees.title_fees
        assert with_fees.creditor_amount == without.creditor_amount  # belongs to the lawyer
        assert with_fees.grand_total == without.grand_total + with_fees.title_fees

    def test_cumulates_with_awarded_fees(self, repo):
        """The motivating case: 20 % of the title + the fees awarded in the enforcement."""
        r = calculate(
            repo, INSTALLMENTS, _params(title_fee_pct=Decimal("20"), awarded_fee_pct=Decimal("10"))
        )
        assert r.title_fees > 0 and r.awarded_fees > 0
        assert r.enforceable_amount == (
            r.net_amount
            + r.awarded_fees
            + r.title_fees
            + r.total_fees_and_expenses
            - r.total_discounts
        )

    def test_523_accrues_on_the_debt_with_the_title_fees(self, repo):
        r = calculate(
            repo, INSTALLMENTS, _params(title_fee_pct=Decimal("20"), fine_523_pct=Decimal("10"))
        )
        assert r.fine_523 == (r.enforceable_amount * 10 / 100).quantize(Decimal("0.01"))

    def test_without_the_field_nothing_changes(self, repo):
        r = calculate(repo, INSTALLMENTS, _params())
        d = r.as_dict()
        assert r.title_fees == Decimal("0.00")
        assert d["totals"]["title_fees"] == "0.00"
        assert d["parameters"]["title_fee_pct"] is None
