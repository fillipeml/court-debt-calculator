"""Calculation statement as a PDF, generated on the server with ReportLab.

The PDF is assembled from the engine's dict (`CalculationResult.as_dict()`), the same source
that feeds the screen and the spreadsheet: no number is recomputed here. No logo or firm name:
the document goes into the court file and must be neutral.
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK = colors.HexColor("#17181C")
ACCENT = colors.HexColor("#047857")
MUTED = colors.HexColor("#6B6F76")
LINE = colors.HexColor("#E4E3DE")
ZEBRA = colors.HexColor("#F2F1EC")
ACCENT_SOFT = colors.HexColor("#ECFDF5")  # background of the "=" milestones of the cascade
NEGATIVE = colors.HexColor("#B91C1C")

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip

INDEX_NAMES = {
    "tjdft": "INPC until 08/2024, IPCA from 09/2024 (Law 14,905/2024)",
    "tjsp": "TJSP practical table: INPC until 07/2024, IPCA-15 from 08/2024",
    "inpc": "INPC for the whole period",
    "ipca": "IPCA for the whole period",
    "ipca15": "IPCA-15 for the whole period",
    "igpm": "IGP-M for the whole period",
    "igpdi": "IGP-DI for the whole period",
}

REGIME_NAMES = {
    "legal": "Legal interest: 1% per month until 29/08/2024, Legal Rate (SGS 29543) from 30/08/2024",
    "legal_rate": "Legal Rate (SGS 29543) for the whole period",
    "fixed": "Fixed monthly percentage (calendar months)",
    "none": "No default interest",
}

FOOTER = (
    "Produced by a deterministic engine over official central-bank indices (SGS API) versioned "
    "in git. Interest follows conventions validated against the TJDFT public calculator "
    "(JuriscalcWeb) and CMN Resolution 5,171/2024. Every total is the exact sum of the displayed "
    "components (CPC art. 524, I)."
)


def brl(value: str | Decimal) -> str:
    text = f"{Decimal(value):,.2f}"
    return "R$ " + text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _six_places(value: str) -> str:
    return f"{Decimal(value):.6f}".replace(".", ",")


def date_br(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def month_in_words(month: str) -> str:
    year, m = month.split("-")
    return f"{MONTHS[int(m) - 1]}/{year}"


class _NumberedCanvas(pdf_canvas.Canvas):
    """Second pass to stamp "Page i of n" on every page."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pages: list[dict] = []

    def showPage(self):  # noqa: N802 - ReportLab API
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self.setFont("Helvetica", 7)
            self.setFillColor(MUTED)
            self.drawRightString(A4[0] - 15 * mm, 8 * mm, f"Page {self._pageNumber} of {total}")
            super().showPage()
        super().save()


def _header_footer(canvas: pdf_canvas.Canvas, _doc) -> None:
    canvas.saveState()
    width, height = A4

    canvas.setFont("Helvetica-Bold", 13)
    canvas.setFillColor(INK)
    canvas.drawString(15 * mm, height - 15 * mm, "CALCULATION STATEMENT")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(
        width - 15 * mm, height - 15 * mm, f"issued on {date.today().strftime('%d/%m/%Y')}"
    )

    # rule with an accent segment
    canvas.setFillColor(LINE)
    canvas.rect(15 * mm, height - 20.5 * mm, width - 30 * mm, 1.1 * mm, stroke=0, fill=1)
    canvas.setFillColor(ACCENT)
    canvas.rect(15 * mm, height - 20.5 * mm, 24 * mm, 1.1 * mm, stroke=0, fill=1)

    footer_style = ParagraphStyle(
        "footer", fontName="Helvetica", fontSize=6.3, leading=7.6, textColor=MUTED
    )
    paragraph = Paragraph(FOOTER, footer_style)
    paragraph.wrap(width - 60 * mm, 20 * mm)
    paragraph.drawOn(canvas, 15 * mm, 6 * mm)

    canvas.restoreState()


def creditor_amount_note(t: dict, p: dict) -> str | None:
    """Composition of the "Creditor's amount". Shown only when it differs from the enforceable
    amount, so the line does not read as an arbitrary number."""
    names = []
    if t["awarded_fees"] != "0.00" and not p.get("awarded_fees_are_the_claim"):
        names.append("awarded")
    if t.get("title_fees", "0.00") != "0.00":
        names.append("title")
    fees = f"{' and '.join(names)} fees" if names else None
    adds_fine = t["fine_523_B"] != "0.00"
    if fees and adds_fine:
        return (
            f"= enforceable amount - {fees} + art. 523 fine "
            "(fees belong to the lawyer, CPC art. 85 §14; the fine belongs to the creditor)"
        )
    if fees:
        return f"= enforceable amount - {fees} (they belong to the lawyer, CPC art. 85 §14)"
    if adds_fine:
        return "= enforceable amount + art. 523 fine (the fine belongs to the creditor)"
    return None


def build_statement_pdf(result: dict, case: dict) -> bytes:
    """result = CalculationResult.as_dict(); case = {number, creditor, debtor}."""
    p = result["parameters"]
    t = result["totals"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=26 * mm,
        bottomMargin=22 * mm,
        title=f"Calculation statement {case.get('number') or ''}".strip(),
    )

    body: list = []
    cell_style = ParagraphStyle(
        "cell", fontName="Helvetica", fontSize=7.5, leading=9, textColor=INK
    )
    section_style = ParagraphStyle(
        "section",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=INK,
        spaceBefore=8,
        spaceAfter=4,
    )

    # -- parameters ---------------------------------------------------------------------
    def par(label: str, value: str) -> list:
        return [Paragraph(f"<b>{label}</b>", cell_style), Paragraph(value, cell_style)]

    regime = REGIME_NAMES.get(p["interest_regime"], p["interest_regime"])
    if p["interest_regime"] == "fixed" and p["fixed_monthly_rate"]:
        rate = f"{Decimal(p['fixed_monthly_rate']):.2f}".replace(".", ",")
        regime = f"Fixed {rate}% per month (calendar months)"

    if p["interest_regime"] == "none":
        interest_period = "—"
    else:
        start = (
            f"from {date_br(p['interest_start'])} "
            if p["interest_start"]
            else "from each amount's date "
        )
        interest_period = start + f"until {date_br(p['interest_end'])}"

    parties = (
        f"{case.get('creditor') or '—'} × {case.get('debtor') or '—'}"
        if case.get("creditor") or case.get("debtor")
        else "—"
    )
    parameters = [
        par("Case", case.get("number") or "—"),
        par("Parties", parties),
        par("Monetary adjustment", INDEX_NAMES.get(p["index"], p["index"])),
        par("Adjusted until", month_in_words(p["adjust_until"])),
        par("Default interest", regime),
        par("Interest period", interest_period),
        par("Final date", date_br(p["final_date"])),
    ]
    params_table = Table(parameters, colWidths=[38 * mm, 142 * mm])
    params_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
            ]
        )
    )
    body.append(params_table)

    # -- line-by-line statement ---------------------------------------------------------
    body.append(Paragraph("Update statement", section_style))

    # the Late fine column appears only when there is a late fine: each line total must be
    # reproducible from the displayed columns (CPC art. 524, I)
    has_fine = t.get("late_fine", "0.00") != "0.00"
    header = ["Date", "Description", "Original", "Factor", "Adjusted", "Interest %", "Interest"]
    header += ["Late fine", "Total"] if has_fine else ["Total"]
    rows: list[list] = [header]
    for line in result["lines"]:
        cells = [
            date_br(line["on"]),
            Paragraph(line["description"] or "", cell_style),
            brl(line["amount"]),
            _six_places(line["factor"]),
            brl(line["adjusted"]),
            _six_places(line["interest_pct"]) + "%",
            brl(line["interest"]),
        ]
        if has_fine:
            cells.append(brl(line["late_fine"]))
        cells.append(brl(line["total"]))
        rows.append(cells)

    totals_row = ["TOTALS", "", brl(t["original"]), "", brl(t["adjusted"]), "", brl(t["interest"])]
    if has_fine:
        totals_row.append(brl(t["late_fine"]))
    totals_row.append(brl(t["gross_total_A"]))
    rows.append(totals_row)

    if has_fine:
        widths = [16 * mm, 28 * mm, 21 * mm, 16 * mm, 21 * mm, 18 * mm, 21 * mm, 18 * mm, 21 * mm]
    else:
        widths = [17 * mm, 37 * mm, 22 * mm, 17 * mm, 22 * mm, 19 * mm, 22 * mm, 24 * mm]
    table = Table(rows, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
        ("FONTNAME", (-1, 1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (-1, 1), (-1, -1), INK),
    ]
    for i in range(2, len(rows) - 1, 2):
        style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    last = len(rows) - 1
    style += [
        ("BACKGROUND", (0, last), (-1, last), ACCENT_SOFT),
        ("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, last), (-1, last), INK),
    ]
    table.setStyle(TableStyle(style))
    body.append(table)

    # -- cascade consolidation, joined to the table's width ------------------------------
    body.append(Spacer(0, 1.5 * mm))

    # original/adjustment/interest/fine/subtotal A are already in the table (TOTALS row): the
    # cascade brings only what is NEW
    cascade: list[tuple[str, str, dict]] = []
    if t["penalty"] != "0.00":
        base = {"gross": "on gross", "adjusted": "on adjusted", "nominal": "on nominal"}.get(
            p["penalty_base"] or "", ""
        )
        cascade.append(
            (
                f"(−) Contractual penalty {p['penalty_pct']}% ({base})",
                "− " + brl(t["penalty"]),
                {"negative": True},
            )
        )
    for d in result["deductions"]:
        cascade.append((f"(−) {d['description']}", "− " + brl(d["amount"]), {"negative": True}))
    if t["total_deductions"] != "0.00":
        cascade.append(("= Net refund", brl(t["net_amount"]), {"strong": True}))
    if t["awarded_fees"] != "0.00":
        if p.get("awarded_fees_are_the_claim"):
            cascade.append(
                (
                    f"(=) Enforced fees {p['awarded_fee_pct']}%: the claim being enforced "
                    "(the base above is not part of the debt)",
                    brl(t["awarded_fees"]),
                    {"strong": True},
                )
            )
        else:
            extra = (
                f" (adjusted claim value: {brl(t['adjusted_claim_value'])})"
                if t.get("adjusted_claim_value")
                else ""
            )
            if has_fine and not p.get("late_fine_in_fee_base"):
                extra += ", base without the late fine"
            cascade.append(
                (f"(+) Awarded fees {p['awarded_fee_pct']}%{extra}", brl(t["awarded_fees"]), {})
            )
    if t.get("title_fees", "0.00") != "0.00":
        suffix = (
            " (over the debt with the fine)"
            if p.get("title_fee_on_fine")
            else (", base without the fine" if has_fine else "")
        )
        cascade.append((f"(+) Title fees {p['title_fee_pct']}%{suffix}", brl(t["title_fees"]), {}))
    entry_labels = {
        "court_fee": "Court fee",
        "expense": "Procedural expense",
        "discount": "Discount/abatement",
    }
    for entry in result.get("entries", []):
        negative = entry["kind"] == "discount"
        label = entry_labels.get(entry["kind"], entry["kind"])
        detail = f": {entry['description']}" if entry["description"] else ""
        cascade.append(
            (
                f"({'−' if negative else '+'}) {label}{detail} ({date_br(entry['on'])}, adjusted)",
                ("− " if negative else "") + brl(entry["adjusted"]),
                {"negative": True} if negative else {},
            )
        )
    if t["enforceable_amount"] != t["gross_total_A"]:
        cascade.append(
            (
                "= Enforceable amount",
                brl(t["enforceable_amount"]),
                {"strong": True, "highlight": True},
            )
        )
    if t["fine_523_B"] != "0.00":
        cascade.append(("(+) Fine, CPC art. 523 §1 (B)", brl(t["fine_523_B"]), {}))
    if t["fee_523_C"] != "0.00":
        cascade.append(("(+) Fees, CPC art. 523 §1 (C)", brl(t["fee_523_C"]), {}))
    cascade.append(("Creditor's amount", brl(t["creditor_amount"]), {}))
    note = creditor_amount_note(t, p)
    if note:
        cascade.append((note, "", {"note": True}))
    if t.get("contract_fees") is not None:
        cascade.append(
            (
                f"Contract fees ({p['contract_fee_pct']}%): informative, not part of the debt",
                "− " + brl(t["contract_fees"]),
                {"info": True},
            )
        )
        cascade.append(
            (
                "Net to the creditor after contract fees",
                brl(t["creditor_after_contract_fees"]),
                {"info": True},
            )
        )

    note_style = ParagraphStyle(
        "cascade_note", fontName="Helvetica-Oblique", fontSize=6.8, leading=8.4, textColor=MUTED
    )
    cascade_rows = [
        [Paragraph(label, note_style) if options.get("note") else label, value]
        for label, value, options in cascade
    ]
    cascade_table = Table(cascade_rows, colWidths=[140 * mm, 40 * mm], hAlign="LEFT")
    cascade_style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
    ]
    for i, (_, _, options) in enumerate(cascade):
        if options.get("strong"):
            cascade_style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
            cascade_style.append(("BACKGROUND", (0, i), (-1, i), ACCENT_SOFT))
            cascade_style.append(("TEXTCOLOR", (0, i), (-1, i), INK))
        if options.get("negative"):
            cascade_style.append(("TEXTCOLOR", (1, i), (1, i), NEGATIVE))
        if options.get("highlight"):
            # the enforceable amount is the number of the petition
            cascade_style.append(("TEXTCOLOR", (1, i), (1, i), ACCENT))
        if options.get("info"):
            cascade_style.append(("TEXTCOLOR", (0, i), (-1, i), MUTED))
            cascade_style.append(("FONTSIZE", (0, i), (-1, i), 7.2))
    cascade_table.setStyle(TableStyle(cascade_style))
    body.append(cascade_table)

    body.append(Spacer(0, 4 * mm))
    total_table = Table(
        [["GRAND TOTAL", brl(t["grand_total"])]], colWidths=[140 * mm, 40 * mm], hAlign="LEFT"
    )
    total_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT),
                ("BOX", (0, 0), (-1, -1), 1.2, ACCENT),
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, 0), INK),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10.5),
                ("TEXTCOLOR", (1, 0), (1, 0), ACCENT),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    body.append(total_table)

    doc.build(
        body, onFirstPage=_header_footer, onLaterPages=_header_footer, canvasmaker=_NumberedCanvas
    )
    return buffer.getvalue()
