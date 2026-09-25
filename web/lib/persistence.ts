/** Local persistence of calculations (the browser's localStorage).
 *
 *  Saved calculations live in THIS browser/machine: there is no database on the server. The
 *  draft is saved automatically on every edit and restored on the next visit. */

import type { DeductionIn, EntryIn, FeeBase, InstallmentIn, InterestRegime, PenaltyBase } from "@/lib/api";

export interface FormState {
  caseInfo: { number: string; creditor: string; debtor: string };
  finalDate: string;
  adjustUntil: string;
  index: string;
  interestRegime: InterestRegime;
  fixedRate: string;
  interestStart: string;
  fine523: boolean;
  fee523: boolean;
  pct523: string;
  penaltyOn: boolean;
  penaltyPct: string;
  penaltyBase: PenaltyBase;
  lateFineOn: boolean;
  lateFinePct: string;
  lateFineInFeeBase: boolean;
  deductions: DeductionIn[];
  entries: EntryIn[];
  awardedOn: boolean;
  awardedPct: string;
  awardedBase: FeeBase;
  awardedIsClaim: boolean;
  contractOn: boolean;
  contractPct: string;
  titleOn: boolean;
  titlePct: string;
  titleOnFine: boolean;
  claimValue: string;
  claimValueMonth: string;
  installments: InstallmentIn[];
}

export interface SavedCalculation {
  id: string;
  name: string;
  createdAt: string; // ISO
  grandTotal: string | null; // the last known total, for the list
  state: FormState;
}

const SAVED_KEY = "court-debt-calculator:saved:v1";
const DRAFT_KEY = "court-debt-calculator:draft:v1";

const hasStorage = () => typeof window !== "undefined" && !!window.localStorage;

export function listSaved(): SavedCalculation[] {
  if (!hasStorage()) return [];
  try {
    const raw = window.localStorage.getItem(SAVED_KEY);
    const list = raw ? (JSON.parse(raw) as SavedCalculation[]) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function saveCalculation(name: string, state: FormState, grandTotal: string | null): SavedCalculation[] {
  const item: SavedCalculation = {
    id: crypto.randomUUID(),
    name: name.trim() || `Calculation of ${new Date().toLocaleDateString("en-GB")}`,
    createdAt: new Date().toISOString(),
    grandTotal,
    state,
  };
  const list = [item, ...listSaved()];
  try {
    window.localStorage.setItem(SAVED_KEY, JSON.stringify(list));
  } catch {
    throw new Error("Could not save: the browser storage is full or blocked.");
  }
  return list;
}

export function deleteCalculation(id: string): SavedCalculation[] {
  const list = listSaved().filter((c) => c.id !== id);
  try {
    window.localStorage.setItem(SAVED_KEY, JSON.stringify(list));
  } catch {
    /* without storage there is nothing to delete */
  }
  return list;
}

export function saveDraft(state: FormState): void {
  if (!hasStorage()) return;
  try {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(state));
  } catch {
    /* full storage: the draft is a convenience and must not break the page */
  }
}

export function readDraft(): FormState | null {
  if (!hasStorage()) return null;
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    return raw ? (JSON.parse(raw) as FormState) : null;
  } catch {
    return null;
  }
}

export function clearDraft(): void {
  if (!hasStorage()) return;
  try {
    window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* idem */
  }
}
