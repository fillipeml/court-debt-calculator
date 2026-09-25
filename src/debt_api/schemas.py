"""Pydantic schemas of the API: they mirror the engine's JSON contract.

Monetary amounts and percentages travel as **decimal strings** ("134000.00", "10"), never
floats, to preserve exactness end to end.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MONTH_REGEX = r"^\d{4}-(0[1-9]|1[0-2])$"


def _valid_decimal(value: str, field: str) -> str:
    try:
        Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{field} is not a valid decimal number: {value!r}") from None
    return value


def _positive_decimal(value: str, field: str) -> str:
    _valid_decimal(value, field)
    if Decimal(value) <= 0:
        raise ValueError(
            f"{field} must be greater than zero: {value!r}. To subtract amounts, use deductions "
            "or entries of kind 'discount'."
        )
    return value


class InstallmentIn(BaseModel):
    amount: str = Field(description="Original amount, decimal string (e.g. '1850.00')")
    on: date = Field(description="Date of the amount: sets the first adjustment month")
    description: str = ""

    @field_validator("amount")
    @classmethod
    def _amount(cls, v: str) -> str:
        return _positive_decimal(v, "installment amount")


class InterestIn(BaseModel):
    regime: Literal["legal", "legal_rate", "fixed", "none"] = "legal"
    fixed_rate: str | None = Field(default=None, description="% per month for the 'fixed' regime")
    start: date | None = Field(
        default=None,
        description="Start (service of process, final judgment...). Null = each installment's date",
    )
    end: date | None = Field(default=None, description="Null = the calculation's final date")

    @field_validator("fixed_rate")
    @classmethod
    def _rate(cls, v: str | None) -> str | None:
        return _valid_decimal(v, "fixed_rate") if v is not None else None


class DeductionIn(BaseModel):
    description: str
    amount: str = Field(description="Fixed amount in BRL, decimal string (e.g. '1097.66')")

    @field_validator("amount")
    @classmethod
    def _amount(cls, v: str) -> str:
        return _positive_decimal(v, "deduction amount")


class EntryIn(BaseModel):
    """Dated entry: adjusted by the calculation's index from its own date, no interest.
    'court_fee'/'expense' add to the enforceable amount; 'discount' subtracts."""

    kind: Literal["court_fee", "expense", "discount"]
    description: str
    amount: str = Field(description="Amount in BRL on the date, decimal string (e.g. '500.00')")
    on: date

    @field_validator("amount")
    @classmethod
    def _amount(cls, v: str) -> str:
        return _positive_decimal(v, "entry amount")


class PenaltyIn(BaseModel):
    pct: str = Field(description="% of the contractual penalty / penalty clause (e.g. '25')")
    base: Literal["gross", "adjusted", "nominal"] = "gross"

    @field_validator("pct")
    @classmethod
    def _pct(cls, v: str) -> str:
        return _valid_decimal(v, "penalty percentage")


class AwardedFeesIn(BaseModel):
    pct: str = Field(description="% of the fees awarded by the court (CPC art. 85)")
    base: Literal["net", "claim_value"] = "net"
    is_the_claim: bool = Field(
        default=False,
        description="True when the fees are THE CLAIM being enforced (enforcement of fees only): "
        "the installments become the base of the calculation and the enforceable amount is the "
        "fees alone; art. 523 accrues on them",
    )
    claim_value: str | None = None
    claim_value_month: str | None = Field(
        default=None,
        pattern=MONTH_REGEX,
        description="Month of the claim value, to adjust it (e.g. '2025-06'); null = nominal",
    )

    @field_validator("pct", "claim_value")
    @classmethod
    def _numbers(cls, v: str | None) -> str | None:
        return _valid_decimal(v, "awarded fees") if v is not None else None


class LateFineIn(BaseModel):
    """Late/contractual fine that ADDS to the debt (Dr. Calc model, case 14): % over the
    adjusted amount of each installment. NOT the contractual penalty (deducts) nor the art. 523
    fine (accrues on the enforceable amount)."""

    pct: str = Field(
        description="% of the fine over each installment's adjusted amount (e.g. '10')"
    )
    in_fee_base: bool = Field(
        default=False,
        description="False (Dr. Calc default, 'not applicable over the fine') = the fine stays out "
        "of the base of the awarded fees",
    )

    @field_validator("pct")
    @classmethod
    def _pct(cls, v: str) -> str:
        return _valid_decimal(v, "late fine percentage")


class TitleFeesIn(BaseModel):
    """Fees provided for in the TITLE itself (e.g. a debt-acknowledgement clause: 'attorney
    fees of 20 % over the total amount of the debt, to which the debtor consents'): they ADD
    to the debt collected from the debtor."""

    pct: str = Field(description="% over the net debt (e.g. '20')")
    on_fine: bool = Field(
        default=False,
        description="True when the clause applies over the debt WITH the late fine (e.g. 'over the "
        "total amount of the debt')",
    )

    @field_validator("pct")
    @classmethod
    def _pct(cls, v: str) -> str:
        return _valid_decimal(v, "title fees percentage")


class CaseIn(BaseModel):
    number: str = ""
    creditor: str = ""
    debtor: str = ""


class CalculationIn(BaseModel):
    final_date: date = Field(description="Final date of the calculation (end of the interest)")
    adjust_until: str = Field(
        pattern=MONTH_REGEX,
        description="Last adjustment month applied (e.g. '2026-04'): explicit, never implicit",
    )
    index: str = Field(
        default="tjdft",
        description="'tjdft' (INPC -> IPCA, Law 14,905), 'tjsp' (TJSP table: INPC -> IPCA-15) or a "
        "single series (inpc, ipca, ipca15, igpm, igpdi...)",
    )
    interest: InterestIn = InterestIn()
    penalty: PenaltyIn | None = Field(
        default=None, description="Contractual penalty deducted from the refund"
    )
    deductions: list[DeductionIn] = Field(
        default_factory=list,
        description="Fixed deductions (assessed usage fee, condominium charges, brokerage...)",
    )
    awarded_fees: AwardedFeesIn | None = Field(
        default=None, description="Fees awarded by the court (CPC art. 85)"
    )
    fine_523_pct: str | None = Field(default=None, description="% of the fine of CPC art. 523 §1")
    fee_523_pct: str | None = Field(default=None, description="% of the fees of CPC art. 523 §1")
    late_fine: LateFineIn | None = Field(
        default=None, description="Late/contractual fine that ADDS (% over the adjusted amount)"
    )
    contract_fee_pct: str | None = Field(
        default=None,
        description="% of the CONTRACT fees (client x law firm): an INFORMATIVE line of the statement "
        "(withholding over the creditor's amount); never part of the debtor's debt",
    )
    title_fees: TitleFeesIn | None = Field(
        default=None,
        description="Fees provided for in the TITLE itself (clause with the debtor's consent): they ADD "
        "to the debt, cumulative with the awarded fees",
    )
    entries: list[EntryIn] = Field(
        default_factory=list,
        description="Court fees/expenses (add) and discounts (subtract), adjusted from their own date",
    )
    installments: list[InstallmentIn] = Field(min_length=1)

    @field_validator("fine_523_pct", "fee_523_pct", "contract_fee_pct")
    @classmethod
    def _pcts(cls, v: str | None) -> str | None:
        return _valid_decimal(v, "percentage") if v is not None else None


class StatementIn(BaseModel):
    """Body of POST /statement: the same calculation + the case identification."""

    case: CaseIn = CaseIn()
    calculation: CalculationIn
