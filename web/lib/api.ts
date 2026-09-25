/** Client of the engine API: the contract mirrors `src/debt_api/schemas.py`.
 *  Money and percentages travel as decimal STRINGS, never numbers. Calls go through the
 *  app's server-side proxy (/api/engine/*), which attaches the API token on the server. */

export const API_URL = "/api/engine";

export interface InstallmentIn {
  amount: string;
  on: string; // YYYY-MM-DD
  description?: string;
}

export interface DeductionIn {
  description: string;
  amount: string;
}

export type EntryKind = "court_fee" | "expense" | "discount";

export interface EntryIn {
  kind: EntryKind;
  description: string;
  amount: string;
  on: string; // YYYY-MM-DD
}

export type InterestRegime = "legal" | "legal_rate" | "fixed" | "none";
export type PenaltyBase = "gross" | "adjusted" | "nominal";
export type FeeBase = "net" | "claim_value";

export interface CalculationIn {
  final_date: string;
  adjust_until: string; // YYYY-MM
  index: string;
  interest: {
    regime: InterestRegime;
    fixed_rate?: string | null;
    start?: string | null;
    end?: string | null;
  };
  penalty?: { pct: string; base: PenaltyBase } | null;
  deductions?: DeductionIn[];
  awarded_fees?: {
    pct: string;
    base: FeeBase;
    is_the_claim?: boolean;
    claim_value?: string | null;
    claim_value_month?: string | null;
  } | null;
  fine_523_pct?: string | null;
  fee_523_pct?: string | null;
  /** late/contractual fine that ADDS (% over each installment's adjusted amount) */
  late_fine?: { pct: string; in_fee_base: boolean } | null;
  /** % of the contract fees: an INFORMATIVE line (withholding over the credit) */
  contract_fee_pct?: string | null;
  /** fees provided for in the TITLE itself: they ADD to the debt */
  title_fees?: { pct: string; on_fine: boolean } | null;
  entries?: EntryIn[];
  installments: InstallmentIn[];
}

export interface LineOut {
  on: string;
  description: string;
  amount: string;
  factor: string;
  adjusted: string;
  adjustment: string;
  interest_pct: string;
  interest: string;
  interest_from: string | null;
  interest_to: string | null;
  late_fine: string; // "0.00" when inactive
  total: string;
}

export interface EntryOut {
  kind: EntryKind;
  description: string;
  on: string;
  amount: string;
  factor: string;
  adjusted: string;
}

export interface Totals {
  original: string;
  adjusted: string;
  interest: string;
  late_fine: string;
  gross_total_A: string;
  penalty: string;
  fixed_deductions: string;
  total_deductions: string;
  net_amount: string;
  awarded_fees: string;
  awarded_fee_base: string;
  title_fees: string;
  title_fee_base: string;
  adjusted_claim_value: string | null;
  fees_and_expenses: string;
  discounts: string;
  enforceable_amount: string;
  fine_523_B: string;
  fee_523_C: string;
  creditor_amount: string;
  contract_fees: string | null;
  creditor_after_contract_fees: string | null;
  grand_total: string;
}

export type Parameters = Record<string, string | boolean | null>;

export interface ResultOut {
  parameters: Parameters;
  deductions: DeductionIn[];
  entries: EntryOut[];
  lines: LineOut[];
  totals: Totals;
}

export interface CaseInfo {
  number: string;
  creditor: string;
  debtor: string;
}

/** Explanatory note of the "Creditor's amount": shows its composition whenever it differs
 *  from the enforceable amount, so the line does not read as an arbitrary number. */
export function creditorAmountNote(t: Totals, parameters: Parameters): string | null {
  const names = [
    t.awarded_fees !== "0.00" && !parameters.awarded_fees_are_the_claim && "awarded",
    (t.title_fees ?? "0.00") !== "0.00" && "title",
  ].filter(Boolean);
  const fees = names.length ? `${names.join(" and ")} fees` : null;
  const addsFine = t.fine_523_B !== "0.00";
  if (fees && addsFine)
    return `= enforceable amount − ${fees} + art. 523 fine (fees belong to the lawyer, CPC art. 85 §14; the fine belongs to the creditor)`;
  if (fees) return `= enforceable amount − ${fees} (they belong to the lawyer, CPC art. 85 §14)`;
  if (addsFine) return "= enforceable amount + art. 523 fine (the fine belongs to the creditor)";
  return null;
}

/** Latest published month per series (e.g. {ipca: "2026-05", ...}). */
export async function latestMonths(): Promise<Record<string, string>> {
  const response = await fetch(`${API_URL}/health`);
  if (!response.ok) throw new Error("API unavailable");
  const body = await response.json();
  return body.latest_months ?? {};
}

export interface ExtractedField {
  value: string | null;
  quote: string | null;
  document?: string | null;
  confidence: number;
}

export interface ExtractedInstallment {
  amount: string;
  on: string;
  description: string;
  quote: string | null;
  document?: string | null;
  confidence: number;
}

export interface RecognisedDocument {
  file_name: string;
  kind: string;
  on: string | null;
  role: string;
}

export interface ExtractedDeduction {
  description: string;
  amount: string;
  quote: string | null;
  document?: string | null;
  confidence: number;
}

export interface ExtractedEntry {
  kind: EntryKind;
  description: string;
  amount: string;
  on: string;
  quote: string | null;
  document?: string | null;
  confidence: number;
}

export interface ExtractionOut {
  simulated: boolean;
  model: string | null;
  extraction: {
    documents: RecognisedDocument[];
    prevailing_decision: ExtractedField;
    settlement: ExtractedField;
    case_number: ExtractedField;
    creditor: ExtractedField;
    debtor: ExtractedField;
    installments: ExtractedInstallment[];
    index: ExtractedField;
    interest_regime: ExtractedField;
    interest_fixed_rate: ExtractedField;
    interest_start: ExtractedField;
    penalty_pct: ExtractedField;
    deductions: ExtractedDeduction[];
    entries: ExtractedEntry[];
    deductions_mentioned: string;
    awarded_fee_pct: ExtractedField;
    awarded_fee_base: ExtractedField;
    awarded_fees_are_the_claim: ExtractedField;
    claim_value: ExtractedField;
    fine_523_pct: ExtractedField;
    fee_523_pct: ExtractedField;
    late_fine_pct: ExtractedField;
    title_fee_pct: ExtractedField;
    notes: string;
  };
}

export async function extract(files: File[]): Promise<ExtractionOut> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  const response = await fetch(`${API_URL}/extract`, { method: "POST", body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "Extraction failed.");
  }
  return response.json();
}

/** Turns FastAPI's validation `detail` (a list of Pydantic errors) into a readable message
 *  that names the field. */
export function readableDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const d = detail[0] as { loc?: (string | number)[]; msg?: string };
    const field = (d.loc ?? []).filter((p) => p !== "body").join(" → ");
    const msg = String(d.msg ?? "invalid value").replace(/^Value error,\s*/i, "");
    return field ? `Field “${field}”: ${msg}` : msg;
  }
  return null;
}

export async function calculate(entry: CalculationIn): Promise<ResultOut> {
  const response = await fetch(`${API_URL}/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entry),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(readableDetail(body?.detail) ?? "Validation error in the calculation parameters.");
  }
  return response.json();
}

/** Downloads the calculation statement as a PDF (generated on the server, neutral). */
export async function downloadStatementPdf(entry: CalculationIn, caseInfo: CaseInfo): Promise<void> {
  const response = await fetch(`${API_URL}/statement`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case: caseInfo, calculation: entry }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "Failed to generate the statement PDF.");
  }
  const name =
    response.headers.get("content-disposition")?.match(/filename="([^"]+)"/)?.[1] ?? "statement.pdf";
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
