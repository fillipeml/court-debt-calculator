# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-09-25

First public release: the English, rebranded port of a calculator built for a litigation team, with fictional demo data.

### Added

- Deterministic engine in `decimal.Decimal`: index repository over nine central-bank series, cumulative adjustment factors, composite indices of two courts (INPC → IPCA, INPC → IPCA-15), the legal-interest timeline (0.5 % → 1 % → Legal Rate) with pro rata by calendar days, fixed monthly rates, and the full cascade (contractual penalty, fixed deductions, late fine, awarded fees over the net amount or the claim value or as the claim itself, title fees, dated court fees and discounts, art. 523 surcharges, creditor's amount, informative contract fees).
- Fourteen reference cases reproducing two public court calculators to the cent, with the decoded conventions documented in `docs/REFERENCE_CASES.md`.
- Ingestion of the central bank's SGS series with continuity validation, retroactive-revision detection and a lag check, plus a daily workflow that commits new months after re-running the goldens.
- FastAPI layer: `/calculate`, `/statement` (ReportLab PDF that reads the engine's dictionary and recomputes nothing), `/extract` (native PDF and spreadsheet reading with structured outputs, quotes and confidences; simulated mode without an API key), `/series`, `/health`, optional bearer-token protection.
- Next.js review app: extraction upload with provenance badges, the full parameter form, the statement with the cascade, PDF and Excel export, a text summary, saved calculations in the browser, a sample-case button, an optional password gate and a server-side proxy that keeps the API token out of the browser.
- CLI (`debt-engine`) for series, factors, adjustments, interest and full calculations from a JSON file.
- 185 Python tests and 51 web checks; CI with lint, tests, a CLI smoke test, the web build and a secret scan.

[0.1.0]: https://github.com/fillipeml/court-debt-calculator/releases/tag/v0.1.0
