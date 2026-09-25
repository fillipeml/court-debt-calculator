"""POST /statement: the PDF carries the same numbers as the golden."""

import io

from fastapi.testclient import TestClient
from pypdf import PdfReader

from debt_api.demo import DEMO_CASE_NUMBER
from debt_api.main import app

client = TestClient(app)

ENTRY = {
    "case": {
        "number": DEMO_CASE_NUMBER,
        "creditor": "Creditor Example",
        "debtor": "Debtor Example Ltd",
    },
    "calculation": {
        "final_date": "2026-05-22",
        "adjust_until": "2026-04",
        "index": "tjdft",
        "interest": {"regime": "legal", "start": "2026-05-15"},
        "fine_523_pct": "10",
        "fee_523_pct": "10",
        "installments": [
            {"amount": "134000.00", "on": "2022-03-02", "description": "Economic benefit"}
        ],
    },
}


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() for page in reader.pages)


class TestStatementPdf:
    def test_valid_pdf_with_the_golden_of_case_05(self):
        response = client.post("/statement", json=ENTRY)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert f"statement-{DEMO_CASE_NUMBER}.pdf" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")

        text = _pdf_text(response.content)
        assert "CALCULATION STATEMENT" in text
        assert DEMO_CASE_NUMBER in text
        # golden of case 05: A, fine, fees and total, to the cent
        assert "162.363,32" in text
        assert "16.236,33" in text
        assert "194.835,98" in text
        assert "art. 524" in text
        assert "Page 1 of" in text

    def test_deductions_appear_in_the_consolidation(self):
        entry = {
            "case": {"number": "", "creditor": "", "debtor": ""},
            "calculation": {
                **ENTRY["calculation"],
                "penalty": {"pct": "25", "base": "gross"},
                "deductions": [
                    {"description": "Outstanding condominium charges", "amount": "1097.66"}
                ],
                "awarded_fees": {"pct": "5", "base": "net"},
            },
        }
        response = client.post("/statement", json=entry)
        assert response.status_code == 200
        text = _pdf_text(response.content)
        assert "Contractual penalty 25%" in text
        assert "Outstanding condominium charges" in text
        assert "40.590,83" in text  # golden penalty
        assert "Enforceable amount" in text
        assert response.headers["content-disposition"].endswith('statement.pdf"')

    def test_late_fine_column_and_contract_fees(self):
        entry = {
            "case": {},
            "calculation": {
                **ENTRY["calculation"],
                "late_fine": {"pct": "10", "in_fee_base": False},
                "contract_fee_pct": "20",
                "awarded_fees": {"pct": "10", "base": "net", "is_the_claim": False},
            },
        }
        response = client.post("/statement", json=entry)
        assert response.status_code == 200
        text = _pdf_text(response.content)
        assert "Late fine" in text
        assert "Contract fees (20%)" in text

    def test_unavailable_index_in_statement_is_422_too(self):
        entry = {"case": {}, "calculation": {**ENTRY["calculation"], "adjust_until": "2027-12"}}
        response = client.post("/statement", json=entry)
        assert response.status_code == 422
        assert "never extrapolates" in response.json()["detail"]
