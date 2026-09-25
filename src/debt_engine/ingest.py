"""Ingestion of the official index series from the Brazilian central bank's SGS API.

Downloads the full history of each configured series, validates monthly continuity and the
absence of retroactive changes, and writes versionable JSON under `indices/data/`. Values are
kept as strings exactly as the API returns them: no conversion to float anywhere.

    update-indices                    # update everything
    update-indices --only ipca,inpc
    update-indices --allow-revision
    update-indices --check-lag

Exit codes:
    0  ok (with or without changes)
    1  network/validation error, or a lag detected with --check-lag
    2  retroactive change detected (needs a human check or --allow-revision)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "indices" / "data"
BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json"
ATTEMPTS = 3


@dataclass(frozen=True)
class Series:
    code: int
    name: str
    unit: str
    max_lag_days: int  # days after the end of the month to consider the series lagging
    note: str = ""


SERIES: dict[str, Series] = {
    "ipca": Series(433, "IPCA", "% per month", 45),
    "inpc": Series(188, "INPC", "% per month", 45),
    "igpm": Series(189, "IGP-M", "% per month", 45),
    "igpdi": Series(190, "IGP-DI", "% per month", 45),
    "ipca15": Series(7478, "IPCA-15", "% per month", 45),
    "selic_monthly": Series(
        4390,
        "SELIC accumulated in the month",
        "% per month",
        40,
        note="The current month is the partial accumulation of the month in progress.",
    ),  # fmt: skip
    "legal_rate": Series(
        29543,
        "Legal Rate (Civil Code art. 406, Law 14,905/2024)",
        "% per month",
        35,
        note="Published by the central bank at the start of each month, for that month (CMN Resolution 5,171/2024).",
    ),  # fmt: skip
    "legal_rate_selic_factor": Series(29541, "Legal Rate: monthly Selic factor", "factor", 35),
    "legal_rate_ipca_factor": Series(29542, "Legal Rate: monthly IPCA factor", "factor", 35),
}


def fetch_series(code: int) -> list[dict]:
    url = BASE_URL.format(code=code)
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "court-debt-calculator-indices/1.0"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https host
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < ATTEMPTS:
                time.sleep(2 * attempt)
    raise RuntimeError(f"Failed to fetch SGS series {code} after {ATTEMPTS} attempts: {last_error}")


def to_months(raw: list[dict], code: int) -> dict[str, str]:
    """Converts [{'data': '01/06/2026', 'valor': '0.24'}] into {'2026-06': '0.24'}."""
    months: dict[str, str] = {}
    for item in raw:
        day, month, year = item["data"].split("/")
        if day != "01":
            raise ValueError(
                f"Series {code}: entry with day {day} ({item['data']}) does not look monthly."
            )
        value = str(item["valor"]).strip()
        try:
            Decimal(value)
        except InvalidOperation:
            raise ValueError(
                f"Series {code}: non-numeric value at {item['data']}: {value!r}"
            ) from None
        key = f"{year}-{month}"
        if key in months:
            raise ValueError(f"Series {code}: duplicate month {key}.")
        months[key] = value
    return months


def validate_continuity(months: dict[str, str], code: int) -> None:
    keys = sorted(months)
    for previous, current in zip(keys, keys[1:], strict=False):
        y, m = map(int, previous.split("-"))
        expected = f"{y + (m == 12):04d}-{(m % 12) + 1:02d}"
        if current != expected:
            raise ValueError(
                f"Series {code}: gap in the monthly series: after {previous} came {current} (expected {expected})."
            )


def detect_revision(old: dict[str, str], new: dict[str, str]) -> list[str]:
    """Months already stored whose value changed, except the most recent of the old file (the
    current month still accumulating, e.g. partial SELIC)."""
    if not old:
        return []
    current = max(old)
    return [
        f"  {key}: {old[key]} -> {new[key]}"
        for key in sorted(old)
        if key != current and key in new and old[key] != new[key]
    ]


def lagging(months: dict[str, str], series: Series, today: date) -> str | None:
    latest = max(months)
    y, m = map(int, latest.split("-"))
    end = date(y + (m == 12), (m % 12) + 1, 1)  # 1st day of the month after the latest one
    lag = (today - end).days
    if lag > series.max_lag_days:
        return (
            f"{series.name} (SGS {series.code}): latest month {latest}, "
            f"{lag} days without a publication (limit {series.max_lag_days})."
        )
    return None


def update(names: list[str], allow_revision: bool) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    had_error = False
    had_revision = False

    for name in names:
        series = SERIES[name]
        target = DATA_DIR / f"{name}.json"
        try:
            raw = fetch_series(series.code)
            new = to_months(raw, series.code)
            validate_continuity(new, series.code)
        except (RuntimeError, ValueError) as exc:
            print(f"[ERROR] {name}: {exc}")
            had_error = True
            continue

        old: dict[str, str] = {}
        if target.exists():
            old = json.loads(target.read_text(encoding="utf-8"))["months"]

        revisions = detect_revision(old, new)
        if revisions and not allow_revision:
            print(f"[RETROACTIVE REVISION] {name}: values already stored changed at the source:")
            print("\n".join(revisions))
            print("  File NOT updated. Confirm with --allow-revision after a human check.")
            had_revision = True
            continue

        if old == new:
            print(f"[ok] {name}: no changes ({len(new)} months, latest {max(new)}).")
            continue

        document = {
            "sgs_series": series.code,
            "name": series.name,
            "unit": series.unit,
            "source": BASE_URL.format(code=series.code),
            "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
            **({"note": series.note} if series.note else {}),
            "months": dict(sorted(new.items())),
        }
        target.write_text(
            json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        added = len(set(new) - set(old))
        print(
            f"[UPDATED] {name}: +{added} month(s), latest {max(new)}"
            + (f" ({len(revisions)} revision(s) accepted)" if revisions else "")
            + "."
        )

    if had_revision:
        return 2
    if had_error:
        return 1
    return 0


def check_lag(names: list[str]) -> int:
    today = date.today()
    alerts = []
    for name in names:
        target = DATA_DIR / f"{name}.json"
        if not target.exists():
            alerts.append(f"{name}: file missing, run the ingestion.")
            continue
        months = json.loads(target.read_text(encoding="utf-8"))["months"]
        alert = lagging(months, SERIES[name], today)
        if alert:
            alerts.append(alert)
    if alerts:
        print("[LAG] Series without a publication inside the expected window:")
        for a in alerts:
            print(f"  - {a}")
        return 1
    print(f"[ok] All {len(names)} series inside the expected publication window.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="comma-separated series (default: all)")
    parser.add_argument(
        "--allow-revision", action="store_true", help="accept retroactive changes of stored values"
    )
    parser.add_argument(
        "--check-lag",
        action="store_true",
        help="only check whether a series is lagging (no update)",
    )
    args = parser.parse_args()

    names = list(SERIES)
    if args.only:
        names = [n.strip() for n in args.only.split(",")]
        unknown = [n for n in names if n not in SERIES]
        if unknown:
            print(f"[ERROR] Unknown series: {', '.join(unknown)}. Available: {', '.join(SERIES)}.")
            return 1

    if args.check_lag:
        return check_lag(names)
    return update(names, args.allow_revision)


if __name__ == "__main__":
    sys.exit(main())
