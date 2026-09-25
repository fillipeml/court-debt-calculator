"""The API: a thin HTTP shell over the deterministic engine.

    debt-api                      (uvicorn with reload; see serve.py)

Endpoints:
    POST /calculate   body = CalculationIn -> structured calculation statement
    POST /statement   body = StatementIn   -> the statement as a PDF
    POST /extract     upload of PDF/xlsx/csv -> parameters extracted by the model
    GET  /series      available index series and their latest month
    GET  /health      status, engine version, extraction mode, latest months

Protection: when the env CALC_API_TOKEN is set, /calculate, /statement and /extract require
the header ``Authorization: Bearer <token>``. Without the env (development), they are open.
"""

from __future__ import annotations

import os
from decimal import Decimal

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from debt_api.extraction import MAX_BYTES_PER_FILE, extract, extraction_mode
from debt_api.schemas import CalculationIn, StatementIn
from debt_api.statement_pdf import build_statement_pdf
from debt_engine import __version__ as engine_version
from debt_engine.calculation import (
    CalculationParameters,
    DatedEntry,
    Deduction,
    Installment,
    calculate,
)
from debt_engine.indices import IndexDataError, IndexRepository

TOKEN_ENV = "CALC_API_TOKEN"


def require_token(request: Request) -> None:
    expected = os.environ.get(TOKEN_ENV)
    if not expected:
        return  # protection off (development)
    received = request.headers.get("authorization", "")
    if received != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Missing or invalid access token.")


app = FastAPI(
    title="Court Debt Calculator API",
    description="Deterministic engine for updating court-ordered debts. The model never does the arithmetic.",
    version=engine_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # the Next.js app in development
    allow_origin_regex=r"https://.*\.vercel\.app",  # the Next.js app deployed on Vercel
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = IndexRepository()


@app.get("/health")
def health() -> dict:
    series = repo.series_available()
    return {
        "status": "ok",
        "engine": engine_version,
        "series": len(series),
        "extraction": extraction_mode(),
        "latest_months": {name: repo.latest_month(name) for name in series},
    }


@app.get("/series")
def series() -> list[dict]:
    return [
        {**repo.metadata(name), "series": name, "latest_month": repo.latest_month(name)}
        for name in repo.series_available()
    ]


@app.post("/extract", dependencies=[Depends(require_token)])
async def extract_endpoint(files: list[UploadFile] = File(...)) -> dict:  # noqa: B008 - FastAPI idiom
    """Extracts calculation parameters from court documents with the model.

    Accepts PDF (including scanned) and spreadsheets (.xlsx or CSV); spreadsheets are converted
    to tabular text before going to the model. Use case 1: judgment + case history (more fields
    filled). Use case 2: the judgment only; what depends on the history comes back "not
    identified" for the lawyer to complete on the review screen. Documents are processed in
    memory and are NOT persisted.
    """
    if not files:
        raise HTTPException(status_code=422, detail="Send at least one file.")
    loaded: list[tuple[str, bytes]] = []
    for upload in files:
        data = await upload.read()
        name = (upload.filename or "document.pdf").strip()
        lower = name.lower()
        is_pdf = data.startswith(b"%PDF")
        is_xlsx = lower.endswith(".xlsx") and data.startswith(b"PK")
        is_csv = lower.endswith(".csv")
        if lower.endswith(".xls") and not is_xlsx:
            raise HTTPException(
                status_code=422,
                detail=f"{name}: the legacy .xls format is not supported; open it in Excel and "
                "save it as .xlsx (or export a PDF).",
            )
        if not (is_pdf or is_xlsx or is_csv):
            raise HTTPException(
                status_code=422, detail=f"{name}: only PDF, Excel (.xlsx) and CSV are accepted."
            )
        if len(data) > MAX_BYTES_PER_FILE:
            raise HTTPException(
                status_code=422,
                detail=f"{name}: larger than {MAX_BYTES_PER_FILE // (1024 * 1024)} MB.",
            )
        loaded.append((name, data))
    try:
        return extract(loaded)
    except Exception as exc:  # an API error becomes a readable message
        raise HTTPException(status_code=502, detail=f"Extraction failed: {exc}") from exc


def _run_calculation(entry: CalculationIn) -> dict:
    fees = entry.awarded_fees
    params = CalculationParameters(
        final_date=entry.final_date,
        adjust_until=entry.adjust_until,
        index=entry.index,
        interest_regime=entry.interest.regime,
        fixed_monthly_rate=Decimal(entry.interest.fixed_rate)
        if entry.interest.fixed_rate
        else None,
        interest_start=entry.interest.start,
        interest_end=entry.interest.end,
        penalty_pct=Decimal(entry.penalty.pct) if entry.penalty else None,
        penalty_base=entry.penalty.base if entry.penalty else "gross",
        deductions=tuple(Deduction(d.description, Decimal(d.amount)) for d in entry.deductions),
        awarded_fee_pct=Decimal(fees.pct) if fees else None,
        awarded_fee_base=fees.base if fees else "net",
        awarded_fees_are_the_claim=fees.is_the_claim if fees else False,
        claim_value=Decimal(fees.claim_value) if fees and fees.claim_value else None,
        claim_value_month=fees.claim_value_month if fees else None,
        fine_523_pct=Decimal(entry.fine_523_pct) if entry.fine_523_pct else None,
        fee_523_pct=Decimal(entry.fee_523_pct) if entry.fee_523_pct else None,
        entries=tuple(
            DatedEntry(e.kind, e.description, Decimal(e.amount), e.on) for e in entry.entries
        ),
        late_fine_pct=Decimal(entry.late_fine.pct) if entry.late_fine else None,
        late_fine_in_fee_base=entry.late_fine.in_fee_base if entry.late_fine else False,
        contract_fee_pct=Decimal(entry.contract_fee_pct) if entry.contract_fee_pct else None,
        title_fee_pct=Decimal(entry.title_fees.pct) if entry.title_fees else None,
        title_fee_on_fine=entry.title_fees.on_fine if entry.title_fees else False,
    )
    installments = [Installment(Decimal(i.amount), i.on, i.description) for i in entry.installments]
    try:
        result = calculate(repo, installments, params)
    except IndexDataError as exc:
        # the engine's golden rule: a missing index is an explicit error, never an extrapolation
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.as_dict()


@app.post("/calculate", dependencies=[Depends(require_token)])
def calculate_endpoint(entry: CalculationIn) -> dict:
    return _run_calculation(entry)


@app.post("/statement", dependencies=[Depends(require_token)])
def statement_endpoint(entry: StatementIn) -> Response:
    """The calculation statement as a PDF: recomputed and rendered on the server."""
    result = _run_calculation(entry.calculation)
    pdf = build_statement_pdf(result, entry.case.model_dump())
    number = "".join(c for c in entry.case.number if c.isdigit() or c in ".-")
    name = f"statement-{number}.pdf" if number else "statement.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
