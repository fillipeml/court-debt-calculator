"""API tests: the golden of case 05 through the whole HTTP layer, plus validation and
protection rules."""

import io
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from debt_api.main import TOKEN_ENV, app

client = TestClient(app)

CASE_05 = {
    "final_date": "2026-05-22",
    "adjust_until": "2026-04",
    "index": "tjdft",
    "interest": {"regime": "legal", "start": "2026-05-15"},
    "fine_523_pct": "10",
    "fee_523_pct": "10",
    "installments": [
        {"amount": "134000.00", "on": "2022-03-02", "description": "Economic benefit"}
    ],
}


class TestCalculate:
    def test_case_05_end_to_end_over_http(self):
        response = client.post("/calculate", json=CASE_05)
        assert response.status_code == 200
        body = response.json()
        assert body["totals"]["gross_total_A"] == "162363.32"
        assert body["totals"]["fine_523_B"] == "16236.33"
        assert body["totals"]["fee_523_C"] == "16236.33"
        assert body["totals"]["grand_total"] == "194835.98"
        assert body["lines"][0]["adjusted"] == "162290.65"
        assert body["lines"][0]["interest"] == "72.67"

    def test_money_travels_as_strings(self):
        body = client.post("/calculate", json=CASE_05).json()
        assert isinstance(body["totals"]["grand_total"], str)
        assert isinstance(body["lines"][0]["amount"], str)

    def test_fees_as_the_claim_being_enforced(self):
        # the enforcement collects ONLY the fees (10 % of the updated benefit = 16,236.33);
        # art. 523 accrues on that debt
        entry = {**CASE_05, "awarded_fees": {"pct": "10", "base": "net", "is_the_claim": True}}
        body = client.post("/calculate", json=entry).json()
        t = body["totals"]
        assert t["gross_total_A"] == "162363.32"  # demonstrated base
        assert t["awarded_fees"] == "16236.33"  # enforced credit
        assert t["enforceable_amount"] == "16236.33"
        assert t["fine_523_B"] == "1623.63"
        assert t["fee_523_C"] == "1623.63"
        assert t["grand_total"] == "19483.59"  # the petition amount + art. 523
        assert body["parameters"]["awarded_fees_are_the_claim"] is True

    def test_tjsp_table_index(self):
        # golden of case 11 (Dr. Calc): R$ 2,500.00 on 10/01/2025, table of Jun/2026
        entry = {
            "final_date": "2026-06-30",
            "adjust_until": "2026-05",
            "index": "tjsp",
            "interest": {"regime": "none"},
            "installments": [{"amount": "2500.00", "on": "2025-01-10"}],
        }
        body = client.post("/calculate", json=entry).json()
        assert body["totals"]["adjusted"] == "2689.21"

    def test_late_fine_case_14(self):
        # a cut of golden 14 (Dr. Calc): item 1 with a 10 % fine over the adjusted amount and
        # 30 % fees that do NOT accrue on the fine
        entry = {
            "final_date": "2026-03-04",
            "adjust_until": "2026-01",
            "index": "inpc",
            "interest": {"regime": "fixed", "fixed_rate": "1.00", "end": "2026-01-31"},
            "late_fine": {"pct": "10", "in_fee_base": False},
            "awarded_fees": {"pct": "30", "base": "net"},
            "installments": [{"amount": "107000.00", "on": "2019-09-29", "description": "Item 1"}],
        }
        body = client.post("/calculate", json=entry).json()
        t = body["totals"]
        line = body["lines"][0]
        assert line["adjusted"] == "151833.57"
        assert line["interest"] == "116911.85"
        assert line["late_fine"] == "15183.36"  # Dr. Calc's FINE column
        assert line["total"] == "283928.78"
        assert t["late_fine"] == "15183.36"
        assert t["gross_total_A"] == "283928.78"
        # 30 % of (283,928.78 - 15,183.36) = 30 % of 268,745.42
        assert t["awarded_fee_base"] == "268745.42"
        assert t["awarded_fees"] == "80623.63"
        assert body["parameters"]["late_fine_pct"] == "10"

    def test_title_fees_add_and_cumulate(self):
        # a debt-acknowledgement clause: 20 % "over the total amount of the debt" (with the
        # fine), cumulated with the fees awarded in the enforcement
        entry = {
            "final_date": "2026-07-31",
            "adjust_until": "2026-06",
            "index": "inpc",
            "interest": {"regime": "fixed", "fixed_rate": "1.00"},
            "late_fine": {"pct": "10", "in_fee_base": False},
            "title_fees": {"pct": "20", "on_fine": True},
            "awarded_fees": {"pct": "10", "base": "net"},
            "installments": [
                {"amount": "29000.00", "on": "2019-09-26", "description": "Down payment"}
            ],
        }
        body = client.post("/calculate", json=entry).json()
        t = body["totals"]
        assert t["title_fee_base"] == t["net_amount"]  # with the fine
        assert Decimal(t["title_fees"]) == (Decimal(t["net_amount"]) * 20 / 100).quantize(
            Decimal("0.01")
        )
        assert Decimal(t["enforceable_amount"]) == (
            Decimal(t["net_amount"]) + Decimal(t["awarded_fees"]) + Decimal(t["title_fees"])
        )
        assert body["parameters"]["title_fee_pct"] == "20"

    def test_contract_fees_are_informative(self):
        # informative line: withheld = pct x creditor's amount; the debt is UNCHANGED
        base = client.post("/calculate", json=CASE_05).json()
        entry = {**CASE_05, "contract_fee_pct": "20"}
        body = client.post("/calculate", json=entry).json()
        t = body["totals"]
        assert t["grand_total"] == base["totals"]["grand_total"]
        assert t["creditor_amount"] == base["totals"]["creditor_amount"]
        assert Decimal(t["contract_fees"]) == (Decimal(t["creditor_amount"]) * 20 / 100).quantize(
            Decimal("0.01")
        )
        assert Decimal(t["creditor_after_contract_fees"]) == Decimal(
            t["creditor_amount"]
        ) - Decimal(t["contract_fees"])
        assert base["totals"]["contract_fees"] is None

    def test_without_late_fine_payload_unchanged(self):
        # regression: a calculation without the field returns a zero fine and A intact
        body = client.post("/calculate", json=CASE_05).json()
        assert body["totals"]["late_fine"] == "0.00"
        assert body["lines"][0]["late_fine"] == "0.00"

    def test_dated_entries_case_12(self):
        # golden Dr. Calc: an adjusted court fee adds, an adjusted discount subtracts
        entry = {
            "final_date": "2026-06-30",
            "adjust_until": "2026-05",
            "index": "tjsp",
            "interest": {"regime": "none"},
            "entries": [
                {
                    "kind": "court_fee",
                    "description": "Court fees",
                    "amount": "500.00",
                    "on": "2025-03-20",
                },
                {
                    "kind": "discount",
                    "description": "Discount",
                    "amount": "300.00",
                    "on": "2026-01-10",
                },
            ],
            "installments": [
                {"amount": "10000.00", "on": "2023-01-15", "description": "Principal credit"},
                {"amount": "2000.00", "on": "2024-06-10", "description": "Partial payment"},
            ],
        }
        body = client.post("/calculate", json=entry).json()
        t = body["totals"]
        assert t["gross_total_A"] == "13896.52"
        assert t["fees_and_expenses"] == "530.72"
        assert t["discounts"] == "309.07"
        assert t["grand_total"] == "14118.17"
        assert body["entries"][0]["adjusted"] == "530.72"

    def test_unavailable_index_is_422_with_an_explicit_message(self):
        entry = {**CASE_05, "adjust_until": "2027-12"}
        response = client.post("/calculate", json=entry)
        assert response.status_code == 422
        assert "never extrapolates" in response.json()["detail"]

    def test_non_decimal_amount_is_rejected(self):
        entry = {**CASE_05, "installments": [{"amount": "abc", "on": "2022-03-02"}]}
        assert client.post("/calculate", json=entry).status_code == 422

    @pytest.mark.parametrize("amount", ["NaN", "nan", "Infinity", "-Infinity", "inf", "sNaN"])
    def test_a_non_finite_amount_is_rejected(self, amount: str):
        """These are valid Decimal literals, which is the whole problem.

        The validator only asked whether Decimal() would parse the string. It parses all of
        these, so the API answered 200 with NaN money totals for the quiet ones and crashed
        with an uncaught InvalidOperation on the signalling ones.
        """
        entry = {**CASE_05, "installments": [{"amount": amount, "on": "2022-03-02"}]}
        assert client.post("/calculate", json=entry).status_code == 422

    def test_negative_or_zero_amounts_are_rejected(self):
        # a negative installment is not an abatement: the right door is a deduction/discount
        for payload in (
            {**CASE_05, "installments": [{"amount": "-500.00", "on": "2022-03-02"}]},
            {**CASE_05, "installments": [{"amount": "0.00", "on": "2022-03-02"}]},
            {**CASE_05, "deductions": [{"description": "x", "amount": "-10.00"}]},
            {
                **CASE_05,
                "entries": [
                    {
                        "kind": "court_fee",
                        "description": "x",
                        "amount": "-10.00",
                        "on": "2024-01-10",
                    }
                ],
            },
        ):
            assert client.post("/calculate", json=payload).status_code == 422

    def test_no_installments_is_422(self):
        entry = {**CASE_05, "installments": []}
        assert client.post("/calculate", json=entry).status_code == 422

    def test_deductions_and_awarded_fees(self):
        entry = {
            **CASE_05,
            "penalty": {"pct": "25", "base": "gross"},
            "deductions": [
                {"description": "Usage fee", "amount": "1399.75"},
                {"description": "Condominium charges", "amount": "1097.66"},
            ],
            "awarded_fees": {"pct": "5", "base": "net"},
        }
        body = client.post("/calculate", json=entry).json()
        t = body["totals"]
        assert t["penalty"] == "40590.83"
        assert t["net_amount"] == "119275.08"
        assert t["awarded_fees"] == "5963.75"
        assert t["enforceable_amount"] == "125238.83"
        assert t["fine_523_B"] == "12523.88"
        assert t["grand_total"] == "150286.59"
        assert len(body["deductions"]) == 2

    def test_fees_over_the_adjusted_claim_value(self):
        entry = {
            **CASE_05,
            "fine_523_pct": None,
            "fee_523_pct": None,
            "awarded_fees": {
                "pct": "10",
                "base": "claim_value",
                "claim_value": "48990.00",
                "claim_value_month": "2025-06",
            },
        }
        body = client.post("/calculate", json=entry).json()
        t = body["totals"]
        assert t["adjusted_claim_value"] is not None
        assert Decimal(t["adjusted_claim_value"]) > Decimal("48990.00")

    def test_fixed_regime(self):
        entry = {
            **CASE_05,
            "interest": {"regime": "fixed", "fixed_rate": "1.0", "start": "2020-03-15"},
            "fine_523_pct": None,
            "fee_523_pct": None,
            "installments": [{"amount": "10000.00", "on": "2020-03-15"}],
        }
        body = client.post("/calculate", json=entry).json()
        assert body["lines"][0]["interest"] == "10689.80"
        assert body["totals"]["grand_total"] == "24942.87"


class TestQueries:
    def test_health(self):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["series"] >= 9
        assert body["extraction"] in ("live", "simulated")
        assert "ipca" in body["latest_months"]

    def test_series(self):
        body = client.get("/series").json()
        names = {s["series"] for s in body}
        assert {"ipca", "inpc", "legal_rate"} <= names


MINIMAL_PDF = b"%PDF-1.4 test content"


class TestExtract:
    def test_simulated_mode_returns_case_01(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        response = client.post(
            "/extract", files={"files": ("judgment.pdf", MINIMAL_PDF, "application/pdf")}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["simulated"] is True
        extraction = body["extraction"]
        assert extraction["installments"][0]["amount"] == "134000.00"
        assert extraction["interest_start"]["value"] == "2026-05-15"
        assert extraction["index"]["value"] == "tjdft"
        # provenance: every filled field carries a quote
        assert extraction["installments"][0]["quote"]
        assert "SIMULATED" in extraction["notes"]
        # multi-document: one entry per attached file + the prevailing decision
        assert extraction["documents"][0]["file_name"] == "judgment.pdf"
        assert extraction["prevailing_decision"]["value"]
        assert extraction["settlement"]["value"] is None

    def test_simulated_mode_with_multiple_files(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        response = client.post(
            "/extract",
            files=[
                ("files", ("appellate.pdf", MINIMAL_PDF, "application/pdf")),
                ("files", ("history.pdf", MINIMAL_PDF, "application/pdf")),
            ],
        )
        assert response.status_code == 200
        docs = response.json()["extraction"]["documents"]
        assert [d["file_name"] for d in docs] == ["appellate.pdf", "history.pdf"]

    def test_accepts_xlsx_and_csv_in_simulated_mode(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["Due date", "Amount paid"])
        ws.append(["10/03/2022", "1.850,00"])
        buf = io.BytesIO()
        wb.save(buf)
        response = client.post(
            "/extract",
            files=[
                (
                    "files",
                    (
                        "history.xlsx",
                        buf.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                ("files", ("installments.csv", b"Date,Amount\n10/03/2022,1850\n", "text/csv")),
            ],
        )
        assert response.status_code == 200
        docs = response.json()["extraction"]["documents"]
        assert [d["file_name"] for d in docs] == ["history.xlsx", "installments.csv"]

    def test_legacy_xls_rejected_with_guidance(self):
        response = client.post(
            "/extract",
            files={"files": ("sheet.xls", b"\xd0\xcf\x11\xe0 blob", "application/vnd.ms-excel")},
        )
        assert response.status_code == 422
        assert "save it as .xlsx" in response.json()["detail"]

    def test_spreadsheet_to_text(self):
        from openpyxl import Workbook

        from debt_api.extraction import spreadsheet_to_text

        wb = Workbook()
        ws = wb.active
        ws.title = "Payments"
        ws.append(["Due date", "Amount paid", "History"])
        ws.append(["10/03/2022", "R$ 1.850,00", "Installment 1"])
        ws.append([None, None, None])  # an empty row is skipped
        buf = io.BytesIO()
        wb.save(buf)
        text = spreadsheet_to_text("history.xlsx", buf.getvalue())
        assert "[ATTACHED SPREADSHEET: history.xlsx" in text
        assert "== SHEET: Payments ==" in text
        assert "10/03/2022 | R$ 1.850,00 | Installment 1" in text

    def test_rejects_non_pdf(self):
        response = client.post("/extract", files={"files": ("note.txt", b"any text", "text/plain")})
        assert response.status_code == 422

    @pytest.mark.parametrize("value", ["proveito econômico atualizado", "claim value"])
    def test_normalisation_of_closed_domain_fields(self, value):
        from debt_api.extraction import ExtractionResult, _normalise, simulated_extraction

        raw = simulated_extraction()["extraction"]
        raw["awarded_fee_base"]["value"] = value
        raw["awarded_fees_are_the_claim"]["value"] = "Sim"
        raw["entries"] = [
            {
                "kind": "custas",
                "description": "x",
                "amount": "1.00",
                "on": "2024-01-01",
                "quote": None,
                "confidence": 0.5,
            },
            {
                "kind": "pagamento",
                "description": "y",
                "amount": "1.00",
                "on": "2024-01-01",
                "quote": None,
                "confidence": 0.5,
            },
        ]
        result = _normalise(ExtractionResult.model_validate(raw))
        assert result.awarded_fee_base.value == ("claim_value" if "claim" in value else "net")
        assert result.awarded_fees_are_the_claim.value == "yes"
        assert [e.kind for e in result.entries] == ["court_fee", "discount"]


class TestTokenProtection:
    def test_open_without_the_env(self, monkeypatch):
        monkeypatch.delenv(TOKEN_ENV, raising=False)
        assert client.post("/calculate", json=CASE_05).status_code == 200

    def test_requires_bearer_with_the_env(self, monkeypatch):
        monkeypatch.setenv(TOKEN_ENV, "test-secret")
        assert client.post("/calculate", json=CASE_05).status_code == 401
        ok = client.post(
            "/calculate", json=CASE_05, headers={"Authorization": "Bearer test-secret"}
        )
        assert ok.status_code == 200

    def test_wrong_token_is_401(self, monkeypatch):
        monkeypatch.setenv(TOKEN_ENV, "test-secret")
        response = client.post(
            "/calculate", json=CASE_05, headers={"Authorization": "Bearer wrong"}
        )
        assert response.status_code == 401

    def test_extract_is_protected_too(self, monkeypatch):
        monkeypatch.setenv(TOKEN_ENV, "test-secret")
        response = client.post(
            "/extract", files={"files": ("j.pdf", MINIMAL_PDF, "application/pdf")}
        )
        assert response.status_code == 401
