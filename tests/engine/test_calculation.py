"""Orchestration: the full calculation end to end.

Reproduces reference cases 01, 02, 04 and 05 through the whole path (installments ->
adjustment -> interest -> art. 523 surcharges), plus unit rules.
"""

import json
from datetime import date
from decimal import Decimal

import pytest

from debt_engine.calculation import (
    CalculationInputError,
    CalculationParameters,
    CalculationResult,
    Installment,
    adjustment_factor,
    calculate,
)

FINAL = date(2026, 5, 22)
BASE = dict(final_date=FINAL, adjust_until="2026-04")


@pytest.fixture(scope="module")
def result_case01(repo) -> CalculationResult:
    return calculate(
        repo,
        [Installment(Decimal("134000.00"), date(2022, 3, 2), "Economic benefit")],
        CalculationParameters(**BASE, interest_start=date(2026, 5, 15)),
    )


@pytest.fixture(scope="module")
def result_case04(repo) -> CalculationResult:
    return calculate(
        repo,
        [
            Installment(Decimal("1850.00"), date(2022, 3, 10), "Installment 1"),
            Installment(Decimal("1850.00"), date(2022, 4, 10), "Installment 2"),
            Installment(Decimal("1920.00"), date(2022, 11, 10), "Installment 3"),
        ],
        CalculationParameters(**BASE, interest_start=date(2023, 6, 1)),
    )


@pytest.fixture(scope="module")
def result_case05(repo) -> CalculationResult:
    return calculate(
        repo,
        [Installment(Decimal("134000.00"), date(2022, 3, 2))],
        CalculationParameters(
            **BASE,
            interest_start=date(2026, 5, 15),
            fine_523_pct=Decimal("10"),
            fee_523_pct=Decimal("10"),
        ),
    )


class TestCase01EndToEnd:
    def test_line(self, result_case01):
        line = result_case01.lines[0]
        assert line.adjusted == Decimal("162290.65")
        assert line.adjustment == Decimal("28290.65")
        assert line.interest == Decimal("72.67")
        assert line.total == Decimal("162363.32")

    def test_totals(self, result_case01):
        assert result_case01.gross_total == Decimal("162363.32")
        assert result_case01.grand_total == Decimal("162363.32")
        assert result_case01.creditor_amount == Decimal("162363.32")

    def test_as_dict_is_json_serialisable(self, result_case01):
        d = result_case01.as_dict()
        assert json.loads(json.dumps(d)) == d
        assert d["totals"]["gross_total_A"] == "162363.32"


class TestCase02EndToEnd:
    def test_fixed_interest_75_months(self, repo):
        result = calculate(
            repo,
            [Installment(Decimal("10000.00"), date(2020, 3, 15))],
            CalculationParameters(
                **BASE,
                interest_regime="fixed",
                fixed_monthly_rate=Decimal("1.0"),
                interest_start=date(2020, 3, 15),
            ),
        )
        line = result.lines[0]
        assert line.adjusted == Decimal("14253.07")
        assert line.interest == Decimal("10689.80")
        assert line.total == Decimal("24942.87")


class TestCase04EndToEnd:
    def test_lines(self, result_case04):
        expected = [
            ("2240.58", "647.05", "2887.63"),
            ("2202.91", "636.17", "2839.08"),
            ("2255.88", "651.47", "2907.35"),
        ]
        for line, (adjusted, interest, total) in zip(result_case04.lines, expected, strict=True):
            assert line.adjusted == Decimal(adjusted)
            assert line.interest == Decimal(interest)
            assert line.total == Decimal(total)

    def test_totals(self, result_case04):
        assert result_case04.total_original == Decimal("5620.00")
        assert result_case04.gross_total == Decimal("8634.06")


class TestCase05EndToEnd:
    def test_art_523_surcharges(self, result_case05):
        assert result_case05.fine_523 == Decimal("16236.33")
        assert result_case05.fee_523 == Decimal("16236.33")

    def test_self_consistent_aggregates(self, result_case05):
        # JuriscalcWeb displays 178,599.64 / 194,835.97 (float64, which does not add up to
        # its own displayed lines)
        assert result_case05.creditor_amount == Decimal("178599.65")
        assert result_case05.grand_total == Decimal("194835.98")


class TestUnitRules:
    def test_default_never_precedes_the_debt(self, repo):
        """An installment later than the interest start accrues interest from its own date."""
        result = calculate(
            repo,
            [Installment(Decimal("1000.00"), date(2026, 5, 18))],
            CalculationParameters(**BASE, interest_start=date(2026, 5, 15)),
        )
        assert result.lines[0].interest_from == date(2026, 5, 18)

    def test_no_interest(self, repo):
        result = calculate(
            repo,
            [Installment(Decimal("1000.00"), date(2025, 1, 10))],
            CalculationParameters(**BASE, interest_regime="none"),
        )
        assert result.lines[0].interest == Decimal("0.00")
        assert result.gross_total == result.lines[0].adjusted

    def test_installment_after_the_adjustment_end_is_not_adjusted(self, repo):
        result = calculate(
            repo,
            [Installment(Decimal("1000.00"), date(2026, 5, 10))],
            CalculationParameters(**BASE, interest_regime="none"),
        )
        assert result.lines[0].factor == Decimal("1")
        assert result.lines[0].adjusted == Decimal("1000.00")

    def test_single_series(self, repo):
        factor = adjustment_factor(repo, "inpc", "2022-03", "2024-08")
        assert factor == repo.cumulative_factor("inpc", "2022-03", "2024-09")

    def test_tjdft_factor_after_the_switch_uses_ipca_only(self, repo):
        factor = adjustment_factor(repo, "tjdft", "2025-01", "2026-04")
        assert factor == repo.cumulative_factor("ipca", "2025-01", "2026-05")

    def test_fixed_regime_without_a_rate_is_an_error(self, repo):
        with pytest.raises(CalculationInputError, match="fixed"):
            calculate(
                repo,
                [Installment(Decimal("1000.00"), date(2025, 1, 10))],
                CalculationParameters(**BASE, interest_regime="fixed"),
            )

    def test_no_installments_is_an_error(self, repo):
        with pytest.raises(CalculationInputError, match="installment"):
            calculate(repo, [], CalculationParameters(**BASE))

    def test_unknown_interest_regime_is_an_error(self, repo):
        with pytest.raises(CalculationInputError, match="interest regime"):
            calculate(
                repo,
                [Installment(Decimal("1000.00"), date(2025, 1, 10))],
                CalculationParameters(**BASE, interest_regime="compound"),
            )
