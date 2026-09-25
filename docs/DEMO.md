# Demo walkthrough (about three minutes)

Everything runs offline. Without an API key the extraction answers in simulated mode with a fictional case; the calculation itself never needs a key.

## 1. The engine from the command line

```bash
uv sync
uv run debt-engine series                                              # the nine central-bank series and their latest month
uv run debt-engine calculate --file docs/sample-case.json              # reference case 05
uv run debt-engine interest --start 2026-05-15 --end 2026-05-22 --regime legal --on 162290.65
uv run debt-engine adjust --index tjsp --amount 1000 --start 2020-03 --end 2026-06
```

The sample case prints the line 134,000.00 → 162,290.65 (+72.67 interest) and the art. 523 surcharges, ending in `GRAND TOTAL: R$ 194.835,98`. Add `--json` to see the structured statement the API returns.

Ask for a month that is not published yet and the engine refuses:

```bash
uv run debt-engine factor --index ipca --start 2026-01 --end 2027-06
# [ERROR] IPCA: month 2026-07 not published/ingested. Latest available: 2026-06. The calculation cannot proceed: the engine never extrapolates indices.
```

## 2. The API

```bash
uv run debt-api                       # http://127.0.0.1:8000, docs at /docs
```

`GET /health` reports the engine version, the extraction mode (`simulated` without a key) and the latest month of every series. `POST /calculate` takes the same JSON as the CLI with English field names (see `src/debt_api/schemas.py`); `POST /statement` returns the PDF.

## 3. The web app

```bash
cd web && npm install && cp .env.example .env && npm run dev    # http://localhost:3000
```

1. Click **Load sample case** in the header: reference case 01 fills the form (one amount, the composite index, legal interest from the final judgment, the art. 523 surcharges).
2. Click **Calculate**. The statement shows the line to the cent, the TOTALS row and the cascade to the grand total of R$ 194.835,98. Hover nothing: every number is the engine's, rendered from the same dictionary as the PDF.
3. Download the **PDF** (neutral, ready for the case file) and the **Excel** (two sheets: statement and consolidation). **Copy summary** puts a text version on the clipboard for an e-mail.
4. Toggle a **Contractual penalty of 25 %**, add a deduction, switch the fees base, add a dated court fee: the cascade grows one labelled line at a time and the enforceable amount is highlighted, because that is the number that goes into the petition.
5. Drop any PDF into **Extraction from documents** and click **Extract parameters**: in simulated mode the form is pre-filled with the fictional case and every field carries a badge with its confidence and, on hover, the excerpt that supports it. With `ANTHROPIC_API_KEY` set on the API, the same flow reads the real documents.

The **Saved** panel keeps calculations in the browser's local storage; the draft is restored on the next visit.

## 4. Updating the indices

```bash
uv run update-indices --check-lag     # is any series late?
uv run update-indices                 # fetch the nine series from the central bank
```

The ingestion validates monthly continuity and stops (exit 2) if a value already stored changed at the source; `--allow-revision` accepts it after a human check. In the repository a scheduled workflow does this daily and commits the new months.
