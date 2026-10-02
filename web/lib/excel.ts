/** Excel in the browser (SheetJS): exports the calculation statement and imports installments
 *  from spreadsheets with a column heuristic. Nothing is uploaded to a server. */

import * as XLSX from "xlsx";
// relative import so the Node test runner can load this module without the "@/" alias
import { creditorAmountNote, type CaseInfo, type InstallmentIn, type ResultOut } from "./api.ts";

const CURRENCY_FORMAT = "#,##0.00";
const ENTRY_LABELS = { court_fee: "Court fee", expense: "Procedural expense", discount: "Discount/abatement" };

function applyFormat(ws: XLSX.WorkSheet, columns: number[], firstRow: number) {
  const range = XLSX.utils.decode_range(ws["!ref"] ?? "A1");
  for (let row = firstRow; row <= range.e.r; row++) {
    for (const column of columns) {
      const cell = ws[XLSX.utils.encode_cell({ r: row, c: column })];
      if (cell && typeof cell.v === "number") cell.z = CURRENCY_FORMAT;
    }
  }
}

const toBR = (iso: string) => iso.split("-").reverse().join("/");

export function exportExcel(result: ResultOut, caseInfo: CaseInfo) {
  const wb = XLSX.utils.book_new();
  const t = result.totals;
  const p = result.parameters;

  // sheet 1: the line-by-line statement (the Late fine column only when there is a fine:
  // each line total is reproducible from the displayed columns)
  const hasFine = t.late_fine !== "0.00";
  const lines = result.lines.map((l) => ({
    Date: toBR(l.on),
    Description: l.description,
    Original: Number(l.amount),
    Factor: Number(Number(l.factor).toFixed(6)),
    Adjusted: Number(l.adjusted),
    "Interest %": Number(Number(l.interest_pct).toFixed(6)),
    Interest: Number(l.interest),
    ...(hasFine ? { "Late fine": Number(l.late_fine) } : {}),
    Total: Number(l.total),
  }));
  const wsStatement = XLSX.utils.json_to_sheet(lines);
  XLSX.utils.sheet_add_aoa(
    wsStatement,
    hasFine
      ? [
          ["TOTALS", "", Number(t.original), "", Number(t.adjusted), "", Number(t.interest), Number(t.late_fine), Number(t.gross_total_A)],
          ["GRAND TOTAL", "", "", "", "", "", "", "", Number(t.grand_total)],
        ]
      : [
          ["TOTALS", "", Number(t.original), "", Number(t.adjusted), "", Number(t.interest), Number(t.gross_total_A)],
          ["GRAND TOTAL", "", "", "", "", "", "", Number(t.grand_total)],
        ],
    { origin: -1 }
  );
  wsStatement["!cols"] = [
    { wch: 16 }, { wch: 32 }, { wch: 14 }, { wch: 10 },
    { wch: 14 }, { wch: 10 }, { wch: 12 },
    ...(hasFine ? [{ wch: 12 }] : []),
    { wch: 16 },
  ];
  applyFormat(wsStatement, hasFine ? [2, 4, 6, 7, 8] : [2, 4, 6, 7], 1);
  XLSX.utils.book_append_sheet(wb, wsStatement, "Statement");

  // sheet 2: the cascade consolidation (mirrors the screen)
  const consolidation: (string | number)[][] = [
    ["CALCULATION STATEMENT"],
    [],
    ["Case", caseInfo.number || "—"],
    ["Creditor", caseInfo.creditor || "—"],
    ["Debtor", caseInfo.debtor || "—"],
    ["Adjusted until", String(p.adjust_until ?? "")],
    ["Final date", toBR(String(p.final_date ?? ""))],
    ["Index", String(p.index ?? "")],
    ["Interest regime", String(p.interest_regime ?? "")],
    [],
    ["Total original", Number(t.original)],
    ["(+) Monetary adjustment", Number(t.adjusted) - Number(t.original)],
    ["(+) Default interest", Number(t.interest)],
  ];
  if (hasFine) consolidation.push([`(+) Late fine ${p.late_fine_pct}% (on adjusted)`, Number(t.late_fine)]);
  consolidation.push(["= Gross subtotal (A)", Number(t.gross_total_A)]);
  if (t.penalty !== "0.00") {
    consolidation.push([`(−) Contractual penalty ${p.penalty_pct}% (base ${p.penalty_base})`, -Number(t.penalty)]);
  }
  for (const d of result.deductions) consolidation.push([`(−) ${d.description}`, -Number(d.amount)]);
  if (t.total_deductions !== "0.00") consolidation.push(["= Net refund", Number(t.net_amount)]);
  if (t.awarded_fees !== "0.00") {
    consolidation.push([
      p.awarded_fees_are_the_claim
        ? `(=) Enforced fees ${p.awarded_fee_pct}%: the claim being enforced`
        : `(+) Awarded fees ${p.awarded_fee_pct}%${hasFine && !p.late_fine_in_fee_base ? ", base without the fine" : ""}`,
      Number(t.awarded_fees),
    ]);
    if (t.adjusted_claim_value) consolidation.push(["    base: adjusted claim value", Number(t.adjusted_claim_value)]);
  }
  if (t.title_fees !== "0.00") {
    consolidation.push([
      `(+) Title fees ${p.title_fee_pct}%${p.title_fee_on_fine ? " (over the debt with the fine)" : ""}`,
      Number(t.title_fees),
    ]);
  }
  for (const e of result.entries ?? []) {
    const sign = e.kind === "discount" ? -1 : 1;
    consolidation.push([
      `(${sign < 0 ? "−" : "+"}) ${ENTRY_LABELS[e.kind]}${e.description ? `: ${e.description}` : ""} (${toBR(e.on)}, adjusted)`,
      sign * Number(e.adjusted),
    ]);
  }
  if (t.enforceable_amount !== t.gross_total_A) consolidation.push(["= Enforceable amount", Number(t.enforceable_amount)]);
  if (t.fine_523_B !== "0.00") consolidation.push(["(+) Fine, CPC art. 523 (B)", Number(t.fine_523_B)]);
  if (t.fee_523_C !== "0.00") consolidation.push(["(+) Fees, CPC art. 523 (C)", Number(t.fee_523_C)]);
  consolidation.push(["Creditor's amount", Number(t.creditor_amount)]);
  const note = creditorAmountNote(t, p);
  if (note) consolidation.push([`    ${note}`]);
  if (t.contract_fees !== null) {
    consolidation.push([`Contract fees (${p.contract_fee_pct}%): informative, not part of the debt`, -Number(t.contract_fees)]);
    consolidation.push(["Net to the creditor after contract fees", Number(t.creditor_after_contract_fees)]);
  }
  consolidation.push(["GRAND TOTAL", Number(t.grand_total)]);
  consolidation.push([]);
  consolidation.push([
    "Deterministic engine · official central-bank indices (SGS API) versioned in git · conventions validated against JuriscalcWeb/TJDFT and CMN Res. 5,171/2024",
  ]);

  const wsConsolidation = XLSX.utils.aoa_to_sheet(consolidation);
  wsConsolidation["!cols"] = [{ wch: 52 }, { wch: 18 }];
  applyFormat(wsConsolidation, [1], 10);
  XLSX.utils.book_append_sheet(wb, wsConsolidation, "Consolidation");

  const name = caseInfo.number ? caseInfo.number.replace(/[^\d.-]/g, "") : "calculation";
  XLSX.writeFile(wb, `statement-${name}.xlsx`);
}

// -- installment import ------------------------------------------------------------------

const DATE_COLUMNS = ["date", "data", "venc", "due", "desemb", "receb", "receipt", "pagamento", "payment", "dt"];
const AMOUNT_COLUMNS = ["amount", "valor", "value", "pago", "paid", "receb", "received", "montante", "parcela", "installment", "quantia"];
const DESCRIPTION_COLUMNS = ["desc", "obs", "hist", "tipo", "type", "referente", "note", "memo"];

export function findColumn(row: Record<string, unknown>, terms: string[]): unknown {
  for (const term of terms) {
    const key = Object.keys(row).find((k) => k.toLowerCase().includes(term));
    if (key !== undefined && row[key] !== "" && row[key] !== null) return row[key];
  }
  return null;
}

export function toISO(raw: unknown): string | null {
  if (raw instanceof Date && !isNaN(raw.getTime())) {
    // Local components, not toISOString. SheetJS builds the cell at LOCAL midnight, which in
    // any UTC+ zone is the previous day in UTC — so every imported payment date moved back
    // one day for a user in Europe, and nowhere for one in Brazil.
    return `${raw.getFullYear()}-${String(raw.getMonth() + 1).padStart(2, "0")}-${String(raw.getDate()).padStart(2, "0")}`;
  }
  if (typeof raw === "string") {
    const br = raw.trim().match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/);
    if (br) return `${br[3]}-${br[2].padStart(2, "0")}-${br[1].padStart(2, "0")}`;
    const iso = raw.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  }
  return null;
}

export function toDecimal(raw: unknown): string | null {
  if (typeof raw === "number" && isFinite(raw) && raw > 0) return raw.toFixed(2);
  if (typeof raw === "string") {
    let text = raw.replace(/[R$\s]/g, "");
    if (text.includes(",")) text = text.replace(/\./g, "").replace(",", ".");
    const number = Number(text);
    if (isFinite(number) && number > 0) return number.toFixed(2);
  }
  return null;
}

export function rowsToInstallments(rows: Record<string, unknown>[]): InstallmentIn[] {
  const installments: InstallmentIn[] = [];
  for (const row of rows) {
    const on = toISO(findColumn(row, DATE_COLUMNS));
    const amount = toDecimal(findColumn(row, AMOUNT_COLUMNS));
    if (!on || !amount) continue;
    const description = findColumn(row, DESCRIPTION_COLUMNS);
    installments.push({ amount, on, description: description ? String(description) : "" });
  }
  return installments;
}

export async function importInstallments(file: File): Promise<InstallmentIn[]> {
  // CSV: raw mode (everything a string). SheetJS's heuristic assumes the AMERICAN format and
  // would corrupt dd/mm dates ("10/03" would become 3 October) and Brazilian amounts
  // ("1850,00" would become 185,000). Our parsers convert.
  const isCSV = file.name.toLowerCase().endsWith(".csv");
  const wb = isCSV
    ? XLSX.read(await file.text(), { type: "string", raw: true })
    : XLSX.read(await file.arrayBuffer(), { cellDates: true });
  const ws = wb.Sheets[wb.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(ws, { defval: "" });
  const installments = rowsToInstallments(rows);

  if (installments.length === 0) {
    throw new Error(
      "No installment recognised: the spreadsheet needs a date column (e.g. 'Date', 'Due date') " +
        "and an amount column (e.g. 'Amount', 'Amount paid')."
    );
  }
  return installments;
}
