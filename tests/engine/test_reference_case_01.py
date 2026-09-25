"""Golden test: reference case 01 (parity to the cent with a public court calculator).

Enforcement of awarded attorney fees; the reference calculation was produced in JuriscalcWeb
(the TJDFT's public calculator, https://juriscalc.tjdft.jus.br) on 22/05/2026. Parameters and
conventions in docs/REFERENCE_CASES.md.

Parameters of the reference calculation:
  Base:       R$ 134,000.00 (economic benefit) on 02/03/2022 (filing date)
  Adjustment: INPC 03/2022..08/2024 + IPCA 09/2024..04/2026 (Law 14,905/2024), full months,
              adjusted "until 04/2026"
  Interest:   Legal Rate (SGS 29543), from 15/05/2026 (final judgment) to 22/05/2026 (final
              date) = 7 days pro rata over the 31 of May, over the adjusted amount
  Fees:       10 % over the updated total

These values are results published by an official court tool and must never change. If this
test breaks, either the ingested data suffered a retroactive revision (see the detector in the
ingestion) or the engine regressed.
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from tests.helpers import cents

BASE_AMOUNT = Decimal("134000.00")
INTEREST_DAYS, DAYS_IN_MAY = Decimal(7), Decimal(31)


@pytest.fixture(scope="module")
def calculation(repo):
    factor = repo.cumulative_factor("inpc", "2022-03", "2024-09") * repo.cumulative_factor(
        "ipca", "2024-09", "2026-05"
    )
    adjusted = BASE_AMOUNT * factor
    interest_pct = repo.monthly_change("legal_rate", "2026-05") * INTEREST_DAYS / DAYS_IN_MAY
    interest = adjusted * interest_pct / 100
    return {
        "factor": factor,
        "adjusted": adjusted,
        "interest_pct": interest_pct,
        "interest": interest,
        "total": adjusted + interest,
    }


class TestJuriscalcWebParity:
    def test_displayed_adjustment_factor(self, calculation):
        pct = ((calculation["factor"] - 1) * 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
        assert pct == Decimal("21.11")

    def test_adjustment_amount(self, calculation):
        assert cents(calculation["adjusted"] - BASE_AMOUNT) == Decimal("28290.65")

    def test_adjusted_amount(self, calculation):
        assert cents(calculation["adjusted"]) == Decimal("162290.65")

    def test_displayed_interest_percentage(self, calculation):
        pct = calculation["interest_pct"].quantize(Decimal("0.000001"), ROUND_HALF_UP)
        assert pct == Decimal("0.044776")

    def test_interest_amount(self, calculation):
        assert cents(calculation["interest"]) == Decimal("72.67")

    def test_calculation_total(self, calculation):
        assert cents(calculation["total"]) == Decimal("162363.32")

    def test_fees_10_pct_over_the_economic_benefit(self, calculation):
        fees = cents(calculation["total"]) * Decimal("0.10")
        assert cents(fees) == Decimal("16236.33")
