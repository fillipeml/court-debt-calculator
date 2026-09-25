"""Golden tests: reference cases 06 to 10 (JuriscalcWeb, generated on 03/07/2026).

They cover what 01 to 05 did not: the complete legal-interest timeline (an installment before
2003), the no-interest regime, pure INPC, a fixed percentage from the service of process and
legal interest from each amount's date (including an installment born in the Legal Rate era).
Conventions in docs/REFERENCE_CASES.md.

Parity: to the cent in money; displayed percentages tolerate ±0.000001 (JuriscalcWeb computes
in float64; this engine is exact Decimal).
"""

from datetime import date
from decimal import Decimal

import pytest

from debt_engine.calculation import CalculationParameters, Installment, calculate
from debt_engine.interest import fixed_monthly_pct, interest_amount, legal_interest_pct
from tests.helpers import adjust_tjdft, cents, pct6

FINAL = date(2026, 5, 22)


class TestCase06CompleteTimeline:
    """R$ 5,000.00 on 15/05/2001; legal interest since 15/05/2001: crosses the THREE eras:
    0.5 % per month (until 10/01/2003), 1 % per month and the Legal Rate.

    DECODED DIVERGENCE (the only one beyond the cent in 10 cases): in the month of the 2002
    Civil Code switch, JuriscalcWeb counts Jan/2003 as 10 days at 0.5 % + **19** days at 1 %,
    so two days of January accrue no interest (10 + 19 = 29 ≠ 31). Exact numeric
    decomposition of its value: 9.935484 + 259.548387 + 13.943206 = 283.427077. This engine
    does not reproduce the hole: 0.5 % in [15/05/2001, 11/01/2003) and 1 % from 11/01/2003
    inclusive (Civil Code art. 406 in force since 11/01/2003): Jan/2003 = 10 + 21 = 31 days.
    Difference: 2/31 of 1 % = 0.064516 p.p. = R$ 14.66 in the creditor's favour."""

    PCT_JC = Decimal("283.427077")
    HOLE_JC = Decimal("2") / Decimal("31")  # 2 days of Jan/2003 at 1 %

    def test_adjusted_amount_25_years(self, repo):
        assert cents(adjust_tjdft(repo, "5000.00", "2001-05")) == Decimal("22717.01")

    def test_legal_pct_three_eras_continuous(self, repo):
        pct = legal_interest_pct(repo, date(2001, 5, 15), FINAL)
        assert pct6(pct) == Decimal("283.491593")  # engine: Jan/2003 without the hole

    def test_jc_pct_reproduced_with_the_2_day_hole(self, repo):
        pct = legal_interest_pct(repo, date(2001, 5, 15), FINAL)
        assert abs(pct6(pct - self.HOLE_JC) - self.PCT_JC) <= Decimal("0.000001")

    def test_jc_values_reproduced_to_the_cent(self, repo):
        adjusted = adjust_tjdft(repo, "5000.00", "2001-05")
        pct_jc = legal_interest_pct(repo, date(2001, 5, 15), FINAL) - self.HOLE_JC
        interest_jc = interest_amount(adjusted, pct_jc)
        assert cents(interest_jc) == Decimal("64386.14")
        assert cents(adjusted) + cents(interest_jc) == Decimal("87103.15")

    def test_engine_values_without_the_hole(self, repo):
        adjusted = adjust_tjdft(repo, "5000.00", "2001-05")
        interest = interest_amount(adjusted, legal_interest_pct(repo, date(2001, 5, 15), FINAL))
        assert cents(interest) == Decimal("64400.80")
        assert cents(adjusted) + cents(interest) == Decimal("87117.81")


class TestCase07NoInterest:
    """R$ 10,000.00 on 20/08/2015; no interest: isolates the monetary adjustment."""

    def test_pure_adjustment(self, repo):
        assert cents(adjust_tjdft(repo, "10000.00", "2015-08")) == Decimal("17419.84")

    def test_calculate_with_regime_none(self, repo):
        result = calculate(
            repo,
            [Installment(Decimal("10000.00"), date(2015, 8, 20), "Single amount, case 07")],
            CalculationParameters(final_date=FINAL, adjust_until="2026-04", interest_regime="none"),
        )
        line = result.lines[0]
        assert line.adjusted == Decimal("17419.84")
        assert line.interest == Decimal("0.00")
        assert result.gross_total == Decimal("17419.84")


class TestCase08PureInpc:
    """R$ 7,500.00 on 10/07/2021; INPC for the whole period.

    The pure INPC adjustment matches JuriscalcWeb to the cent.

    JURISCALCWEB QUIRK DISCOVERED HERE (the 'legal interest' radio confirmed checked by DOM
    inspection): with the index "INPC (for the whole period)" it does NOT apply the Legal Rate
    switch: it computes 1 % per month by calendar months until the end (59 months = exactly
    59.00 %, Jul/2021 -> May/2026, no pro rata). This engine keeps the Law 14,905/2024
    timeline whatever the adjustment index (Civil Code art. 406 changed for everyone);
    JuriscalcWeb's result is reproducible here with the 'fixed' 1 % regime.
    """

    def test_pure_inpc_adjustment(self, repo):
        adjusted = Decimal("7500.00") * repo.cumulative_factor("inpc", "2021-07", "2026-05")
        assert cents(adjusted) == Decimal("9760.68")

    def test_interest_as_jc_computes_59_months(self, repo):
        assert fixed_monthly_pct("1.0", date(2021, 7, 10), FINAL) == Decimal("59.0")
        adjusted = Decimal("7500.00") * repo.cumulative_factor("inpc", "2021-07", "2026-05")
        interest = interest_amount(adjusted, Decimal("59.0"))
        assert cents(interest) == Decimal("5758.80")
        assert cents(adjusted) + cents(interest) == Decimal("15519.48")

    def test_documented_divergence_engine_keeps_the_legal_rate(self, repo):
        """The engine's LEGAL interest for the same period: 1 % pro rata until 29/08/2024 +
        Legal Rate, lower than JuriscalcWeb's 59 % (the Legal Rate runs below 1 % per month
        in the period)."""
        engine_pct = legal_interest_pct(repo, date(2021, 7, 10), FINAL)
        assert engine_pct < Decimal("59.0")
        assert engine_pct > Decimal("45.0")  # sanity: order of magnitude


class TestCase09FixedFromService:
    """Two installments; fixed 1 % per month from the service of process (15/02/2023):
    inclusive calendar months Feb/2023 -> May/2026 = 40 months for both."""

    def test_40_months(self):
        assert fixed_monthly_pct("1.0", date(2023, 2, 15), FINAL) == Decimal("40.0")

    def test_full_calculation(self, repo):
        result = calculate(
            repo,
            [
                Installment(Decimal("3000.00"), date(2022, 6, 10), "Installment 1"),
                Installment(Decimal("3000.00"), date(2022, 9, 10), "Installment 2"),
            ],
            CalculationParameters(
                final_date=FINAL,
                adjust_until="2026-04",
                interest_regime="fixed",
                fixed_monthly_rate=Decimal("1.0"),
                interest_start=date(2023, 2, 15),
            ),
        )
        l1, l2 = result.lines
        assert (l1.adjusted, l1.interest, l1.total) == (
            Decimal("3519.68"),
            Decimal("1407.87"),
            Decimal("4927.55"),
        )
        assert (l2.adjusted, l2.interest, l2.total) == (
            Decimal("3530.05"),
            Decimal("1412.02"),
            Decimal("4942.07"),
        )
        assert result.gross_total == Decimal("9869.62")


@pytest.fixture(scope="module")
def result_case10(repo):
    return calculate(
        repo,
        [
            Installment(Decimal("2000.00"), date(2023, 1, 10), "Installment 1"),
            Installment(Decimal("2500.00"), date(2023, 7, 15), "Installment 2"),
            Installment(
                Decimal("3000.00"), date(2024, 10, 5), "Installment 3, after the Legal Rate"
            ),
        ],
        CalculationParameters(final_date=FINAL, adjust_until="2026-04", interest_regime="legal"),
    )


class TestCase10InterestFromEachAmountsDate:
    """Three installments; legal interest from each amount's date (no common start): the 3rd
    installment (05/10/2024) is born in the Legal Rate era and adjusted by IPCA only."""

    EXPECTED = [
        ("2324.94", "33.588367", "780.91", "3105.85"),
        ("2830.12", "27.427077", "776.22", "3606.34"),
        ("3256.80", "13.137057", "427.85", "3684.65"),
    ]

    def test_lines_to_the_cent(self, result_case10):
        for line, (adjusted, pct, interest, total) in zip(
            result_case10.lines, self.EXPECTED, strict=True
        ):
            assert line.adjusted == Decimal(adjusted)
            assert abs(pct6(line.interest_pct) - Decimal(pct)) <= Decimal("0.000001")
            assert line.interest == Decimal(interest)
            assert line.total == Decimal(total)

    def test_grand_total(self, result_case10):
        assert result_case10.gross_total == Decimal("10396.84")
