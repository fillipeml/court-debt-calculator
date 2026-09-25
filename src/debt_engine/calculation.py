"""Orchestration of the full calculation: installments, adjustment, interest and surcharges.

Reproduces the structure of the court statement (CPC, art. 524, I): each line itemises the
original amount, the adjustment factor, the adjusted amount, the interest and the total.
**Self-consistency**: every total is the exact sum of the rounded components displayed, never
the rounding of a raw sum (see the note on JuriscalcWeb in docs/REFERENCE_CASES.md).

Conventions (validated in reference cases 01 to 05):
* Adjustment by full month: an amount dated any day of month M receives the full change of M
  onwards, up to the month `adjust_until` (an EXPLICIT parameter: "the latest published
  month" is a decision of whoever calculates, never implicit).
* Composite indices (Law 14,905/2024): "tjdft" = INPC up to the month 08/2024 and full IPCA
  from 09/2024; "tjsp" (the São Paulo court's practical table) = INPC up to 07/2024 and
  IPCA-15 from 08/2024, valid for months >= Aug/1995. Any single series of `indices/data` is
  accepted too.
* Interest per installment: from the later of the configured start and the installment's own
  date (default never precedes the debt), until `interest_end` (default: the final date),
  convention `[start, end)`.
* Fine and fees of CPC art. 523, §1: a percentage over the enforceable amount; the fees do not
  belong to the creditor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from debt_engine.indices import IndexDataError, IndexRepository, next_month
from debt_engine.interest import fixed_monthly_pct, legal_interest_pct, legal_rate_pct

LAW_14905_SWITCH = "2024-09"  # first month adjusted by IPCA in the "tjdft" index
CENT = Decimal("0.01")

INTEREST_REGIMES = ("legal", "legal_rate", "fixed", "none")
PENALTY_BASES = ("gross", "adjusted", "nominal")
FEE_BASES = ("net", "claim_value")
ENTRY_KINDS = ("court_fee", "expense", "discount")


def cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _month_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


class CalculationInputError(IndexDataError):
    """A parameter of the calculation is invalid or inconsistent."""


@dataclass(frozen=True)
class Installment:
    """An amount to update: its date sets the first adjustment month and the interest start
    in the 'from each amount's date' mode."""

    amount: Decimal
    on: date
    description: str = ""


@dataclass(frozen=True)
class Deduction:
    """Fixed-amount deduction from the refund (assessed usage fee, condominium charges,
    brokerage...). Percentage deductions use the contractual penalty."""

    description: str
    amount: Decimal


@dataclass(frozen=True)
class DatedEntry:
    """Dated entry, adjusted by the calculation's index from its own date until `adjust_until`,
    WITHOUT interest (mechanics validated against Dr. Calc, case 12): 'court_fee' and 'expense'
    ADD to the enforceable amount; 'discount' (recognised abatement/payment) SUBTRACTS, also
    adjusted."""

    kind: str  # court_fee | expense | discount
    description: str
    amount: Decimal
    on: date


@dataclass(frozen=True)
class AdjustedEntry:
    entry: DatedEntry
    factor: Decimal
    adjusted_raw: Decimal  # unrounded

    @property
    def adjusted(self) -> Decimal:
        return cents(self.adjusted_raw)


@dataclass(frozen=True)
class CalculationParameters:
    final_date: date
    adjust_until: str  # last adjustment month applied (e.g. "2026-04")
    index: str = (
        "tjdft"  # composite (tjdft, tjsp) or a single series (inpc, ipca, ipca15, igpm, igpdi...)
    )
    interest_regime: str = "legal"  # legal | legal_rate | fixed | none
    fixed_monthly_rate: Decimal | None = None  # % per month, required by the "fixed" regime
    interest_start: date | None = None  # None = from each installment's date
    interest_end: date | None = None  # None = final_date
    # deductions from the refund (real-estate rescissions)
    penalty_pct: Decimal | None = None  # contractual penalty / penalty clause, in %
    penalty_base: str = "gross"  # gross (adjusted + interest) | adjusted | nominal
    deductions: tuple[Deduction, ...] = ()  # fixed deductions in BRL
    # fees awarded by the court to the winning party (CPC art. 85)
    awarded_fee_pct: Decimal | None = None
    awarded_fee_base: str = "net"  # net | claim_value
    claim_value: Decimal | None = None
    claim_value_month: str | None = None  # when given, the claim value is adjusted
    # True = the awarded fees ARE the claim being enforced (enforcement of fees only): the
    # installments become the base of the calculation only and the enforceable amount is the
    # fees alone (art. 523 accrues on them). Modelled after a real enforcement petition (case 13).
    awarded_fees_are_the_claim: bool = False
    # enforcement surcharges (CPC art. 523, §1)
    fine_523_pct: Decimal | None = None
    fee_523_pct: Decimal | None = None
    # dated entries (court fees, expenses, discounts): adjusted, no interest
    entries: tuple[DatedEntry, ...] = ()
    # late-payment / contractual fine that ADDS to the debt (Dr. Calc model, case 14): % over the
    # ADJUSTED amount of each installment, rounded per installment. NOT the contractual penalty
    # (which DEDUCTS) nor the art. 523 fine (which accrues on the enforceable amount at the end).
    late_fine_pct: Decimal | None = None
    # CONTRACT fees (client x law firm), INFORMATIVE: % over the creditor's amount, shown on the
    # statement as "how much will be withheld from the credit". NEVER part of the debtor's debt
    # (not enforceable against the debtor); changes no total of the calculation.
    contract_fee_pct: Decimal | None = None
    # fees provided for in the TITLE itself (contract / debt-acknowledgement clause with the
    # debtor's express consent, e.g. "20 % attorney fees over the total debt"): ADD to the
    # debt, next to the awarded fees. Base: net refund; the late fine enters the base only with
    # title_fee_on_fine=True ("total debt").
    title_fee_pct: Decimal | None = None
    title_fee_on_fine: bool = False
    # False (Dr. Calc default, "not applicable over the fine") = the late fine stays OUT of the
    # base of the awarded fees.
    late_fine_in_fee_base: bool = False


@dataclass(frozen=True)
class CalculationLine:
    installment: Installment
    factor: Decimal
    adjusted_raw: Decimal  # unrounded
    interest_pct: Decimal  # accumulated %, unrounded
    interest_raw: Decimal  # unrounded
    interest_from: date | None
    interest_to: date | None
    # % of the late fine (None = no fine), over the line's adjusted amount, rounded per line
    # (parity with Dr. Calc's FINE column)
    late_fine_pct: Decimal | None = None

    @property
    def adjusted(self) -> Decimal:
        return cents(self.adjusted_raw)

    @property
    def adjustment(self) -> Decimal:
        return self.adjusted - cents(self.installment.amount)

    @property
    def interest(self) -> Decimal:
        return cents(self.interest_raw)

    @property
    def late_fine(self) -> Decimal:
        if not self.late_fine_pct:
            return Decimal("0.00")
        # over the DISPLAYED (rounded) adjusted amount, not the raw one: whoever checks the
        # statement reproduces the fine from the printed value (art. 524, I), and it is also
        # Dr. Calc's behaviour (case 14)
        return cents(self.adjusted * self.late_fine_pct / 100)

    @property
    def total(self) -> Decimal:
        return self.adjusted + self.interest + self.late_fine


@dataclass(frozen=True)
class CalculationResult:
    parameters: CalculationParameters
    lines: tuple[CalculationLine, ...]
    adjusted_claim_value: Decimal | None = None  # filled when the claim value is adjusted
    entries: tuple[AdjustedEntry, ...] = ()

    @property
    def total_original(self) -> Decimal:
        return sum((cents(line.installment.amount) for line in self.lines), Decimal("0"))

    @property
    def total_adjusted(self) -> Decimal:
        return sum((line.adjusted for line in self.lines), Decimal("0"))

    @property
    def total_interest(self) -> Decimal:
        return sum((line.interest for line in self.lines), Decimal("0"))

    @property
    def total_late_fine(self) -> Decimal:
        """Late/contractual fine that ADDS (case 14): the sum of the per-line fines (% over the
        adjusted amount, rounded per line, like Dr. Calc)."""
        return sum((line.late_fine for line in self.lines), Decimal("0"))

    @property
    def gross_total(self) -> Decimal:
        """(A), gross subtotal: the sum of the line totals (adjusted + interest + late fine when
        active)."""
        return sum((line.total for line in self.lines), Decimal("0"))

    # -- deductions from the refund --------------------------------------------------------
    @property
    def penalty_base(self) -> Decimal:
        base = self.parameters.penalty_base
        if base == "gross":
            # the documented definition of "gross" is adjusted + interest: the late fine (a
            # creditor's surcharge) stays out of the penalty base
            return self.gross_total - self.total_late_fine
        if base == "adjusted":
            return self.total_adjusted
        return self.total_original  # nominal

    @property
    def penalty(self) -> Decimal:
        pct = self.parameters.penalty_pct
        return cents(self.penalty_base * pct / 100) if pct else Decimal("0.00")

    @property
    def total_fixed_deductions(self) -> Decimal:
        return sum((cents(d.amount) for d in self.parameters.deductions), Decimal("0"))

    @property
    def total_deductions(self) -> Decimal:
        return self.penalty + self.total_fixed_deductions

    @property
    def net_amount(self) -> Decimal:
        return self.gross_total - self.total_deductions

    # -- fees awarded by the court (CPC art. 85) -----------------------------------------
    @property
    def awarded_fee_base(self) -> Decimal:
        if self.parameters.awarded_fee_base == "claim_value":
            base = self.adjusted_claim_value or self.parameters.claim_value or Decimal("0")
            return cents(base)
        if not self.parameters.late_fine_in_fee_base:
            # Dr. Calc default ("not applicable over the fine"): the late fine stays out of the
            # base of the awarded fees
            return self.net_amount - self.total_late_fine
        return self.net_amount

    @property
    def awarded_fees(self) -> Decimal:
        pct = self.parameters.awarded_fee_pct
        return cents(self.awarded_fee_base * pct / 100) if pct else Decimal("0.00")

    # -- fees of the title (clause of the title: ADD to the debt) ------------------------
    @property
    def title_fee_base(self) -> Decimal:
        if self.parameters.title_fee_on_fine:
            return self.net_amount
        return self.net_amount - self.total_late_fine

    @property
    def title_fees(self) -> Decimal:
        pct = self.parameters.title_fee_pct
        return cents(self.title_fee_base * pct / 100) if pct else Decimal("0.00")

    # -- dated entries (court fees, expenses, discounts) ---------------------------------
    @property
    def total_fees_and_expenses(self) -> Decimal:
        return sum(
            (e.adjusted for e in self.entries if e.entry.kind in ("court_fee", "expense")),
            Decimal("0"),
        )

    @property
    def total_discounts(self) -> Decimal:
        return sum((e.adjusted for e in self.entries if e.entry.kind == "discount"), Decimal("0"))

    # -- enforcement surcharges (art. 523) -----------------------------------------------
    @property
    def enforceable_amount(self) -> Decimal:
        """Base of art. 523: the debt enforced = net amount + awarded fees + title fees +
        adjusted court fees/expenses - adjusted discounts. Without deductions, fees and entries
        it equals (A).

        With `awarded_fees_are_the_claim`: the enforcement is of the fees ONLY; the installments
        are just the base of the calculation and the enforceable amount is `awarded_fees`
        (+ fees/expenses - discounts)."""
        if self.parameters.awarded_fees_are_the_claim:
            return (
                self.awarded_fees
                + self.title_fees
                + self.total_fees_and_expenses
                - self.total_discounts
            )
        return (
            self.net_amount
            + self.awarded_fees
            + self.title_fees
            + self.total_fees_and_expenses
            - self.total_discounts
        )

    @property
    def fine_523(self) -> Decimal:
        pct = self.parameters.fine_523_pct
        return cents(self.enforceable_amount * pct / 100) if pct else Decimal("0.00")

    @property
    def fee_523(self) -> Decimal:
        pct = self.parameters.fee_523_pct
        return cents(self.enforceable_amount * pct / 100) if pct else Decimal("0.00")

    @property
    def creditor_amount(self) -> Decimal:
        if self.parameters.awarded_fees_are_the_claim:
            return (
                self.awarded_fees
                + self.total_fees_and_expenses
                - self.total_discounts
                + self.fine_523
            )
        return self.net_amount + self.total_fees_and_expenses - self.total_discounts + self.fine_523

    # -- contract fees (informative, never part of the debt) -----------------------------
    @property
    def contract_fees(self) -> Decimal | None:
        pct = self.parameters.contract_fee_pct
        if not pct:
            return None
        return cents(self.creditor_amount * pct / 100)

    @property
    def creditor_after_contract_fees(self) -> Decimal | None:
        withheld = self.contract_fees
        return None if withheld is None else self.creditor_amount - withheld

    @property
    def grand_total(self) -> Decimal:
        return self.enforceable_amount + self.fine_523 + self.fee_523

    def as_dict(self) -> dict:
        p = self.parameters
        opt = lambda v: str(v) if v else None  # noqa: E731
        return {
            "parameters": {
                "final_date": p.final_date.isoformat(),
                "adjust_until": p.adjust_until,
                "index": p.index,
                "interest_regime": p.interest_regime,
                "fixed_monthly_rate": opt(p.fixed_monthly_rate),
                "interest_start": p.interest_start.isoformat() if p.interest_start else None,
                "interest_end": (p.interest_end or p.final_date).isoformat(),
                "penalty_pct": opt(p.penalty_pct),
                "penalty_base": p.penalty_base,
                "awarded_fee_pct": opt(p.awarded_fee_pct),
                "awarded_fee_base": p.awarded_fee_base,
                "awarded_fees_are_the_claim": p.awarded_fees_are_the_claim,
                "fine_523_pct": opt(p.fine_523_pct),
                "fee_523_pct": opt(p.fee_523_pct),
                "late_fine_pct": opt(p.late_fine_pct),
                "late_fine_in_fee_base": p.late_fine_in_fee_base,
                "contract_fee_pct": opt(p.contract_fee_pct),
                "title_fee_pct": opt(p.title_fee_pct),
                "title_fee_on_fine": p.title_fee_on_fine,
            },
            "deductions": [
                {"description": d.description, "amount": str(cents(d.amount))} for d in p.deductions
            ],
            "entries": [
                {
                    "kind": e.entry.kind,
                    "description": e.entry.description,
                    "on": e.entry.on.isoformat(),
                    "amount": str(cents(e.entry.amount)),
                    "factor": str(e.factor),
                    "adjusted": str(e.adjusted),
                }
                for e in self.entries
            ],
            "lines": [
                {
                    "on": line.installment.on.isoformat(),
                    "description": line.installment.description,
                    "amount": str(cents(line.installment.amount)),
                    "factor": str(line.factor),
                    "adjusted": str(line.adjusted),
                    "adjustment": str(line.adjustment),
                    "interest_pct": str(line.interest_pct),
                    "interest": str(line.interest),
                    "interest_from": line.interest_from.isoformat() if line.interest_from else None,
                    "interest_to": line.interest_to.isoformat() if line.interest_to else None,
                    "late_fine": str(line.late_fine),
                    "total": str(line.total),
                }
                for line in self.lines
            ],
            "totals": {
                "original": str(self.total_original),
                "adjusted": str(self.total_adjusted),
                "interest": str(self.total_interest),
                "late_fine": str(self.total_late_fine),
                "gross_total_A": str(self.gross_total),
                "penalty": str(self.penalty),
                "fixed_deductions": str(self.total_fixed_deductions),
                "total_deductions": str(self.total_deductions),
                "net_amount": str(self.net_amount),
                "awarded_fees": str(self.awarded_fees),
                "awarded_fee_base": str(self.awarded_fee_base),
                "title_fees": str(self.title_fees),
                "title_fee_base": str(self.title_fee_base),
                "adjusted_claim_value": str(cents(self.adjusted_claim_value))
                if self.adjusted_claim_value is not None
                else None,
                "fees_and_expenses": str(self.total_fees_and_expenses),
                "discounts": str(self.total_discounts),
                "enforceable_amount": str(self.enforceable_amount),
                "fine_523_B": str(self.fine_523),
                "fee_523_C": str(self.fee_523),
                "creditor_amount": str(self.creditor_amount),
                # informative (None when not configured): never added to the debt
                "contract_fees": str(self.contract_fees)
                if self.contract_fees is not None
                else None,
                "creditor_after_contract_fees": str(self.creditor_after_contract_fees)
                if self.creditor_after_contract_fees is not None
                else None,
                "grand_total": str(self.grand_total),
            },
        }


# Composite indices per court table: (series before, series after, switch month, minimum
# supported month). The Law 14,905/2024 switch differs by court, decoded empirically against
# the benchmarks:
# * TJDFT (JuriscalcWeb): full IPCA from the month SEP/2024;
# * TJSP practical table (Dr. Calc): IPCA-15 from the month AUG/2024 (the Sep/2024 table, the
#   first under the new law, already incorporated August's IPCA-15; verified month by month at
#   the boundary).
# Reading equivalence: "TJSP table of month M" = adjust_until M-1 (the Jun/2026 table applies
# indices up to the month May/2026).
# The TJSP table is only reproducible with our series from Aug/1995 (before that: ORTN/OTN/IPC/
# IPC-r, not ingested; golden rule: explicit error, never approximate).
COMPOSITE_INDICES: dict[str, tuple[str, str, str, str | None]] = {
    "tjdft": ("inpc", "ipca", LAW_14905_SWITCH, None),
    "tjsp": ("inpc", "ipca15", "2024-08", "1995-08"),
}


def adjustment_factor(
    repo: IndexRepository, index: str, from_month: str, adjust_until: str
) -> Decimal:
    """Adjustment factor from the month `from_month` to `adjust_until` (both inclusive). An
    installment later than the end of the adjustment is not adjusted."""
    if from_month > adjust_until:
        return Decimal("1")
    limit = next_month(adjust_until)
    if index not in COMPOSITE_INDICES:
        return repo.cumulative_factor(index, from_month, limit)
    before, after, switch, minimum = COMPOSITE_INDICES[index]
    if minimum and from_month < minimum:
        raise IndexDataError(
            f"The '{index}' table is only reproduced by this engine from the month {minimum} "
            f"(before that it uses historical indices not yet ingested: ORTN/OTN/IPC/IPC-r for the "
            f"TJSP). Month requested: {from_month}. The engine never approximates an index."
        )
    if from_month >= switch:
        return repo.cumulative_factor(after, from_month, limit)
    if limit <= switch:
        return repo.cumulative_factor(before, from_month, limit)
    return repo.cumulative_factor(before, from_month, switch) * repo.cumulative_factor(
        after, switch, limit
    )


def _interest_pct(
    repo: IndexRepository, p: CalculationParameters, start: date, end: date
) -> Decimal:
    if p.interest_regime == "none" or start >= end:
        return Decimal("0")
    if p.interest_regime == "legal":
        return legal_interest_pct(repo, start, end)
    if p.interest_regime == "legal_rate":
        return legal_rate_pct(repo, start, end)
    if p.interest_regime == "fixed":
        if p.fixed_monthly_rate is None:
            raise CalculationInputError("The 'fixed' interest regime requires fixed_monthly_rate.")
        return fixed_monthly_pct(p.fixed_monthly_rate, start, end)
    raise CalculationInputError(
        f"Unknown interest regime: {p.interest_regime!r}. Valid: {', '.join(INTEREST_REGIMES)}."
    )


def calculate(
    repo: IndexRepository, installments: list[Installment], p: CalculationParameters
) -> CalculationResult:
    if not installments:
        raise CalculationInputError("No installment given.")
    if p.penalty_base not in PENALTY_BASES:
        raise CalculationInputError(
            f"Unknown penalty base: {p.penalty_base!r}. Valid: {', '.join(PENALTY_BASES)}."
        )
    if p.awarded_fee_base not in FEE_BASES:
        raise CalculationInputError(
            f"Unknown fee base: {p.awarded_fee_base!r}. Valid: {', '.join(FEE_BASES)}."
        )
    if p.awarded_fee_base == "claim_value" and p.awarded_fee_pct and p.claim_value is None:
        raise CalculationInputError("Fees over the claim value require the claim_value field.")
    if p.awarded_fees_are_the_claim and not p.awarded_fee_pct:
        raise CalculationInputError(
            "Fees as the claim being enforced require the percentage (awarded_fee_pct)."
        )
    for entry in p.entries:
        if entry.kind not in ENTRY_KINDS:
            raise CalculationInputError(
                f"Unknown entry kind: {entry.kind!r}. Valid: {', '.join(ENTRY_KINDS)}."
            )
    adjusted_claim_value: Decimal | None = None
    if p.claim_value is not None and p.claim_value_month:
        claim_factor = adjustment_factor(repo, p.index, p.claim_value_month, p.adjust_until)
        adjusted_claim_value = Decimal(p.claim_value) * claim_factor

    adjusted_entries = []
    for entry in p.entries:
        entry_factor = adjustment_factor(repo, p.index, _month_of(entry.on), p.adjust_until)
        adjusted_entries.append(
            AdjustedEntry(
                entry=entry, factor=entry_factor, adjusted_raw=Decimal(entry.amount) * entry_factor
            )
        )

    lines = []
    interest_end = p.interest_end or p.final_date
    for installment in installments:
        factor = adjustment_factor(repo, p.index, _month_of(installment.on), p.adjust_until)
        adjusted = Decimal(installment.amount) * factor

        if p.interest_regime == "none":
            interest_from = interest_to = None
            pct = Decimal("0")
        else:
            # default never precedes the debt: the later date prevails
            interest_from = max(p.interest_start or installment.on, installment.on)
            interest_to = interest_end
            pct = _interest_pct(repo, p, interest_from, interest_to)

        lines.append(
            CalculationLine(
                installment=installment,
                factor=factor,
                adjusted_raw=adjusted,
                interest_pct=pct,
                interest_raw=adjusted * pct / 100,
                interest_from=interest_from,
                interest_to=interest_to,
                late_fine_pct=p.late_fine_pct,
            )
        )
    return CalculationResult(
        parameters=p,
        lines=tuple(lines),
        adjusted_claim_value=adjusted_claim_value,
        entries=tuple(adjusted_entries),
    )
