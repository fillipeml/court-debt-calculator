"""Golden: reference case 14, a late fine that ADDS + fees without the fine (Dr. Calc, a real
acceptance-test spreadsheet of 29/07/2026, with the amounts kept and the parties removed).

Benchmark: Dr. Calc's "COURT DEBT SPREADSHEET" generated on 04/03/2026 for the enforcement of
an extrajudicial title: INPC, update Feb/2026, simple interest of 1 % per month, "a 10.00 %
addition for the fine" and "attorney fees of 30.00 %, not applicable over the fine", 11 court
fees and 4 dated discounts/abatements.

DECODED mechanics of the fine and the fees:

* fine = 10 % over the UPDATED amount (adjusted, no interest) of each item, quantised PER
  ITEM (FINE column: 15,183.36 = 10 % of 151,833.57);
* item total = updated + interest + fine (283,928.78);
* fees "not applicable over the fine": 30 % of (subtotal - fine) = 30 % of 269,845.98 =
  80,953.79.

Dr. Calc reading conventions (the same as case 12):

* "Update date of the amounts: February/2026" = indices up to the month JANUARY/2026
  (adjust_until="2026-01", the "M-1" rule);
* interest counted by ANNIVERSARY until the calculation date (04/03/2026): item 1:
  29/09/2019 -> 77 months. Our convention (inclusive calendar months, the JuriscalcWeb
  standard) produces the SAME count with interest_end in Jan/2026: 09/2019 -> 01/2026
  inclusive = 77 (checked for the 6 installments).

This makes the WHOLE spreadsheet verifiable to the cent, up to the GRAND TOTAL.
"""

from datetime import date
from decimal import Decimal

import pytest

from debt_engine.calculation import CalculationParameters, DatedEntry, Installment, calculate

INSTALLMENTS = [
    Installment(Decimal("107000.00"), date(2019, 9, 29), "Item 1 (principal)"),
    Installment(Decimal("479.84"), date(2024, 8, 12), "Item 13"),
    Installment(Decimal("51.66"), date(2024, 12, 6), "Item 14"),
    Installment(Decimal("131.50"), date(2024, 12, 6), "Item 15"),
    Installment(Decimal("229.12"), date(2025, 6, 13), "Item 16"),
    Installment(Decimal("28.41"), date(2025, 10, 17), "Item 17"),
]

COURT_FEES = [
    ("2023-02-13", "10003.47"), ("2023-02-23", "10.34"), ("2023-04-13", "789.00"),
    ("2023-05-22", "789.00"), ("2023-07-18", "51.66"), ("2023-09-12", "526.00"),
    ("2024-01-17", "131.50"), ("2024-02-01", "657.50"), ("2024-04-16", "370.66"),
    ("2024-06-13", "53.30"), ("2024-06-20", "53.30"),
]  # fmt: skip
DISCOUNTS = [
    ("2024-09-04", "48701.92"), ("2025-02-17", "71660.02"),
    ("2025-09-08", "163751.07"), ("2025-09-19", "61879.90"),
]  # fmt: skip


def _entries():
    items = [
        DatedEntry("court_fee", "Court fee", Decimal(v), date.fromisoformat(d))
        for d, v in COURT_FEES
    ]
    items += [
        DatedEntry("discount", "Discount/abatement", Decimal(v), date.fromisoformat(d))
        for d, v in DISCOUNTS
    ]
    return tuple(items)


@pytest.fixture(scope="module")
def result(repo):
    return calculate(
        repo,
        INSTALLMENTS,
        CalculationParameters(
            final_date=date(2026, 3, 4),
            adjust_until="2026-01",  # Dr. Calc's "update Feb/2026" = M-1
            index="inpc",
            interest_regime="fixed",
            fixed_monthly_rate=Decimal("1.00"),
            # Jan/2026 reproduces Dr. Calc's anniversary count up to 04/03/2026 (see docstring)
            interest_end=date(2026, 1, 31),
            late_fine_pct=Decimal("10"),
            late_fine_in_fee_base=False,
            awarded_fee_pct=Decimal("30"),
            awarded_fee_base="net",
            entries=_entries(),
        ),
    )


class TestCase14LateFine:
    def test_adjusted_to_the_cent(self, result):
        expected = ["151833.57", "509.35", "54.14", "137.82", "232.37", "28.60"]
        assert [str(line.adjusted) for line in result.lines] == expected
        assert result.total_adjusted == Decimal("152795.85")

    def test_interest_pct_equivalent_to_the_anniversary_count(self, result):
        assert [int(line.interest_pct) for line in result.lines] == [77, 18, 14, 14, 8, 4]

    def test_interest_to_the_cent(self, result):
        expected = ["116911.85", "91.68", "7.58", "19.29", "18.59", "1.14"]
        assert [str(line.interest) for line in result.lines] == expected
        assert result.total_interest == Decimal("117050.13")

    def test_fine_per_item_to_the_cent(self, result):
        """Dr. Calc's FINE column: 10 % of the adjusted amount, quantised per item."""
        expected = ["15183.36", "50.94", "5.41", "13.78", "23.24", "2.86"]
        assert [str(line.late_fine) for line in result.lines] == expected
        assert result.total_late_fine == Decimal("15279.59")

    def test_item_total_includes_the_fine(self, result):
        assert str(result.lines[0].total) == "283928.78"
        assert result.gross_total == Decimal("285125.57")  # Dr. Calc subtotal

    def test_fees_do_not_accrue_on_the_fine(self, result):
        assert result.awarded_fee_base == Decimal("269845.98")
        assert result.awarded_fees == Decimal("80953.79")

    def test_fees_and_discounts_to_the_cent(self, result):
        assert result.total_fees_and_expenses == Decimal("15054.52")
        assert result.total_discounts == Decimal("354817.01")

    def test_dr_calc_grand_total(self, result):
        # 285,125.57 + 80,953.79 + 15,054.52 - 354,817.01 = 26,316.87
        assert result.enforceable_amount == Decimal("26316.87")
        assert result.grand_total == Decimal("26316.87")

    def test_self_consistency_with_the_fine(self, result):
        """CPC art. 524, I: every total is the exact sum of the displayed components."""
        assert (
            result.gross_total
            == result.total_adjusted + result.total_interest + result.total_late_fine
        )
        sum_of_lines = sum((line.total for line in result.lines), Decimal("0"))
        assert sum_of_lines == result.gross_total

    def test_dict_exposes_the_fine(self, result):
        d = result.as_dict()
        assert d["totals"]["late_fine"] == "15279.59"
        assert d["lines"][0]["late_fine"] == "15183.36"
        assert d["parameters"]["late_fine_pct"] == "10"
        assert d["parameters"]["late_fine_in_fee_base"] is False


class TestLateFineRules:
    def test_without_the_fine_nothing_changes(self, repo):
        """Regression: late_fine_pct=None preserves the current behaviour."""
        base = calculate(
            repo,
            INSTALLMENTS[:2],
            CalculationParameters(
                final_date=date(2026, 3, 4),
                adjust_until="2026-02",
                index="inpc",
                interest_regime="fixed",
                fixed_monthly_rate=Decimal("1.00"),
            ),
        )
        assert base.total_late_fine == Decimal("0.00")
        assert base.gross_total == base.total_adjusted + base.total_interest
        assert base.as_dict()["totals"]["late_fine"] == "0.00"

    def test_fine_may_enter_the_fee_base(self, repo):
        """The late_fine_in_fee_base=True variant (without Dr. Calc's checkbox)."""
        r = calculate(
            repo,
            INSTALLMENTS[:1],
            CalculationParameters(
                final_date=date(2026, 3, 4),
                adjust_until="2026-02",
                index="inpc",
                interest_regime="none",
                late_fine_pct=Decimal("10"),
                late_fine_in_fee_base=True,
                awarded_fee_pct=Decimal("30"),
            ),
        )
        assert r.awarded_fee_base == r.net_amount

    def test_gross_penalty_base_stays_without_the_fine(self, repo):
        """'Gross' for the penalty is still adjusted + interest (the fine out of the base)."""
        r = calculate(
            repo,
            INSTALLMENTS[:1],
            CalculationParameters(
                final_date=date(2026, 3, 4),
                adjust_until="2026-02",
                index="inpc",
                interest_regime="none",
                late_fine_pct=Decimal("10"),
                penalty_pct=Decimal("10"),
                penalty_base="gross",
            ),
        )
        assert r.penalty_base == r.total_adjusted
