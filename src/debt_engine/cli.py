"""Command line of the engine.

    debt-engine series
    debt-engine factor --index ipca --start 2024-09 --end 2026-06
    debt-engine adjust --index ipca --amount 1850.00 --start 2024-09 --end 2026-06
    debt-engine interest --start 2026-05-15 --end 2026-05-22 --regime legal [--on 162290.65]
    debt-engine calculate --file case.json [--json]

Format of the JSON for `calculate`:
    {
      "final_date": "2026-05-22",
      "adjust_until": "2026-04",
      "index": "tjdft",
      "interest": {"regime": "legal", "start": "2026-05-15"},
      "fine_523_pct": "10",
      "fee_523_pct": "10",
      "installments": [{"amount": "134000.00", "on": "2022-03-02", "description": "..."}]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from debt_engine.calculation import CalculationParameters, Installment, calculate
from debt_engine.indices import IndexDataError, IndexRepository
from debt_engine.interest import (
    fixed_monthly_pct,
    interest_amount,
    legal_interest_pct,
    legal_rate_pct,
)


def fmt_brl(amount: Decimal) -> str:
    rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    integer, _, decimals = f"{rounded:,.2f}".partition(".")
    return "R$ " + integer.replace(",", ".") + "," + decimals


def cmd_series(repo: IndexRepository, _args: argparse.Namespace) -> None:
    for name in repo.series_available():
        meta = repo.metadata(name)
        print(
            f"{name:26} SGS {meta['sgs_series']:>6}  latest: {repo.latest_month(name)}  ({meta['name']})"
        )


def cmd_factor(repo: IndexRepository, args: argparse.Namespace) -> None:
    factor = repo.cumulative_factor(args.index, args.start, args.end)
    print(
        f"Cumulative factor {args.index.upper()} from {args.start} to {args.end}: "
        f"{factor.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)}"
    )


def cmd_adjust(repo: IndexRepository, args: argparse.Namespace) -> None:
    amount = Decimal(args.amount)
    factor = repo.cumulative_factor(args.index, args.start, args.end)
    print(f"Index:     {args.index.upper()} ({args.start} -> {args.end})")
    print(f"Factor:    {factor.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)}")
    print(f"Original:  {fmt_brl(amount)}")
    print(f"Adjusted:  {fmt_brl(amount * factor)}")


def cmd_interest(repo: IndexRepository, args: argparse.Namespace) -> None:
    if args.regime == "fixed":
        if not args.rate:
            raise SystemExit("--regime fixed requires --rate (e.g. --rate 1.0)")
        rate = Decimal(args.rate.replace(",", "."))
        pct = fixed_monthly_pct(rate, args.start, args.end)
        regime = f"fixed {rate}% per month (inclusive calendar months)"
    elif args.regime == "legal-rate":
        pct = legal_rate_pct(repo, args.start, args.end)
        regime = "Legal Rate (CMN Res. 5,171/2024, simple interest, pro rata die)"
    else:
        pct = legal_interest_pct(repo, args.start, args.end)
        regime = "Legal interest (0.5% until 10/01/2003; 1% per month; Legal Rate from 30/08/2024)"
    print(f"Regime:               {regime}")
    print(f"Period:               [{args.start} -> {args.end})")
    print(f"Accumulated interest: {pct.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)}%")
    if args.on:
        print(f"Base (adjusted):      {fmt_brl(Decimal(args.on))}")
        print(f"Interest amount:      {fmt_brl(interest_amount(args.on, pct))}")


def cmd_calculate(repo: IndexRepository, args: argparse.Namespace) -> None:
    with open(args.file, encoding="utf-8") as fh:
        data = json.load(fh)
    interest = data.get("interest", {})
    params = CalculationParameters(
        final_date=date.fromisoformat(data["final_date"]),
        adjust_until=data["adjust_until"],
        index=data.get("index", "tjdft"),
        interest_regime=interest.get("regime", "legal"),
        fixed_monthly_rate=Decimal(interest["fixed_rate"]) if interest.get("fixed_rate") else None,
        interest_start=date.fromisoformat(interest["start"]) if interest.get("start") else None,
        interest_end=date.fromisoformat(interest["end"]) if interest.get("end") else None,
        fine_523_pct=Decimal(data["fine_523_pct"]) if data.get("fine_523_pct") else None,
        fee_523_pct=Decimal(data["fee_523_pct"]) if data.get("fee_523_pct") else None,
    )
    installments = [
        Installment(Decimal(x["amount"]), date.fromisoformat(x["on"]), x.get("description", ""))
        for x in data["installments"]
    ]
    result = calculate(repo, installments, params)

    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=1))
        return

    print(
        f"{'Date':<12}{'Amount':>14}{'Factor':>12}{'Adjusted':>14}{'Interest %':>12}{'Interest':>13}{'Total':>14}"
    )
    for line in result.lines:
        print(
            f"{line.installment.on.strftime('%d/%m/%Y'):<12}"
            f"{fmt_brl(line.installment.amount):>14}"
            f"{line.factor.quantize(Decimal('0.000001'), ROUND_HALF_UP):>12}"
            f"{fmt_brl(line.adjusted):>14}"
            f"{line.interest_pct.quantize(Decimal('0.000001'), ROUND_HALF_UP):>11}%"
            f"{fmt_brl(line.interest):>13}"
            f"{fmt_brl(line.total):>14}"
        )
    print("-" * 91)
    print(f"Gross total (A):          {fmt_brl(result.gross_total)}")
    if result.fine_523:
        print(f"Art. 523 fine (B):        {fmt_brl(result.fine_523)}")
    if result.fee_523:
        print(f"Art. 523 fees (C):        {fmt_brl(result.fee_523)}")
    print(f"Creditor's amount:        {fmt_brl(result.creditor_amount)}")
    print(f"GRAND TOTAL:              {fmt_brl(result.grand_total)}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="debt-engine", description=__doc__)
    parser.add_argument("--data", help="alternative indices/data directory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("series", help="list the available series and their latest month")

    p_factor = sub.add_parser("factor", help="cumulative adjustment factor")
    p_adjust = sub.add_parser("adjust", help="adjust a monetary amount")
    for p in (p_factor, p_adjust):
        p.add_argument("--index", required=True)
        p.add_argument("--start", required=True, metavar="YYYY-MM")
        p.add_argument("--end", required=True, metavar="YYYY-MM")
    p_adjust.add_argument("--amount", required=True)

    p_interest = sub.add_parser("interest", help="percentage and amount of default interest")
    p_interest.add_argument(
        "--start", required=True, metavar="YYYY-MM-DD", help="first day (counts)"
    )
    p_interest.add_argument(
        "--end", required=True, metavar="YYYY-MM-DD", help="end date (does not count)"
    )
    p_interest.add_argument("--regime", choices=["legal", "legal-rate", "fixed"], default="legal")
    p_interest.add_argument("--rate", metavar="PCT", help="monthly rate in %% for --regime fixed")
    p_interest.add_argument(
        "--on", metavar="AMOUNT", help="adjusted amount to apply the interest to"
    )

    p_calc = sub.add_parser("calculate", help="full calculation from a JSON parameter file")
    p_calc.add_argument("--file", required=True, help="path of the JSON (see the docstring)")
    p_calc.add_argument("--json", action="store_true", help="JSON output (structured statement)")

    args = parser.parse_args()
    repo = IndexRepository(args.data)
    commands = {
        "series": cmd_series,
        "factor": cmd_factor,
        "adjust": cmd_adjust,
        "interest": cmd_interest,
        "calculate": cmd_calculate,
    }
    try:
        commands[args.command](repo, args)
    except IndexDataError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
