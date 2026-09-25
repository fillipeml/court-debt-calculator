"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import DatePicker from "@/components/date-picker";
import MonthPicker from "@/components/month-picker";
import { AiBadge, Card, Pills, Spinner, Toggle, labelClass } from "@/components/ui";
import {
  calculate,
  creditorAmountNote,
  downloadStatementPdf,
  extract,
  latestMonths,
  type CalculationIn,
  type CaseInfo,
  type DeductionIn,
  type EntryIn,
  type EntryKind,
  type ExtractionOut,
  type FeeBase,
  type InstallmentIn,
  type InterestRegime,
  type PenaltyBase,
  type ResultOut,
} from "@/lib/api";
import { exportExcel, importInstallments } from "@/lib/excel";
import { brl, dateBR, formatAmountBR, monthLabel, parseAmountBR, parsePct, previousMonth, today } from "@/lib/format";
import {
  clearDraft,
  deleteCalculation,
  listSaved,
  readDraft,
  saveCalculation,
  saveDraft,
  type FormState,
  type SavedCalculation,
} from "@/lib/persistence";

const ENTRY_LABELS: Record<EntryKind, string> = {
  court_fee: "Court fee",
  expense: "Procedural expense",
  discount: "Discount / abatement",
};

const PASSWORD_GATE = process.env.NEXT_PUBLIC_PASSWORD_GATE === "true";
const REPO_URL = "https://github.com/fillipeml/court-debt-calculator";

/** Reference case 01: the golden case validated to the cent against a public court
 *  calculator (docs/REFERENCE_CASES.md). One click shows the engine at work. */
const SAMPLE_CASE: Partial<FormState> = {
  caseInfo: { number: "0001234-25.2099.8.99.0001", creditor: "Creditor (fictional)", debtor: "Debtor (fictional)" },
  finalDate: "2026-05-22",
  adjustUntil: "2026-04",
  index: "tjdft",
  interestRegime: "legal",
  interestStart: "2026-05-15",
  fine523: true,
  fee523: true,
  pct523: "10",
  installments: [{ amount: "134000.00", on: "2022-03-02", description: "Economic benefit" }],
};

const emptyState = (adjustUntil: string): FormState => ({
  caseInfo: { number: "", creditor: "", debtor: "" },
  finalDate: today(),
  adjustUntil,
  index: "tjdft",
  interestRegime: "legal",
  fixedRate: "1,00",
  interestStart: "",
  fine523: false,
  fee523: false,
  pct523: "10",
  penaltyOn: false,
  penaltyPct: "25",
  penaltyBase: "gross",
  lateFineOn: false,
  lateFinePct: "10",
  lateFineInFeeBase: false,
  deductions: [],
  entries: [],
  awardedOn: false,
  awardedPct: "10",
  awardedBase: "net",
  awardedIsClaim: false,
  contractOn: false,
  contractPct: "30",
  titleOn: false,
  titlePct: "20",
  titleOnFine: false,
  claimValue: "",
  claimValueMonth: "",
  installments: [],
});

export default function Page() {
  const router = useRouter();
  const [caseInfo, setCaseInfo] = useState<CaseInfo>({ number: "", creditor: "", debtor: "" });
  const [finalDate, setFinalDate] = useState(today());
  const [adjustUntil, setAdjustUntil] = useState(previousMonth());
  const [latestPublished, setLatestPublished] = useState<string | undefined>();
  const [index, setIndex] = useState("tjdft");
  const [interestRegime, setInterestRegime] = useState<InterestRegime>("legal");
  const [fixedRate, setFixedRate] = useState("1,00");
  const [interestStart, setInterestStart] = useState("");
  const [fine523, setFine523] = useState(false);
  const [fee523, setFee523] = useState(false);
  const [pct523, setPct523] = useState("10");

  const [penaltyOn, setPenaltyOn] = useState(false);
  const [penaltyPct, setPenaltyPct] = useState("25");
  const [penaltyBase, setPenaltyBase] = useState<PenaltyBase>("gross");
  const [lateFineOn, setLateFineOn] = useState(false);
  const [lateFinePct, setLateFinePct] = useState("10");
  const [lateFineInFeeBase, setLateFineInFeeBase] = useState(false);
  const [deductions, setDeductions] = useState<DeductionIn[]>([]);
  const [newDeduction, setNewDeduction] = useState({ description: "", amount: "" });
  const [entries, setEntries] = useState<EntryIn[]>([]);
  const [newEntry, setNewEntry] = useState<EntryIn>({ kind: "court_fee", description: "", amount: "", on: "" });

  const [awardedOn, setAwardedOn] = useState(false);
  const [awardedPct, setAwardedPct] = useState("10");
  const [awardedBase, setAwardedBase] = useState<FeeBase>("net");
  const [awardedIsClaim, setAwardedIsClaim] = useState(false);
  const [contractOn, setContractOn] = useState(false);
  const [contractPct, setContractPct] = useState("30");
  const [titleOn, setTitleOn] = useState(false);
  const [titlePct, setTitlePct] = useState("20");
  const [titleOnFine, setTitleOnFine] = useState(false);
  const [claimValue, setClaimValue] = useState("");
  const [claimValueMonth, setClaimValueMonth] = useState("");

  const [installments, setInstallments] = useState<InstallmentIn[]>([]);
  const [newInstallment, setNewInstallment] = useState({ amount: "", on: "", description: "" });
  const [justAdded, setJustAdded] = useState(-1);

  const [result, setResult] = useState<ResultOut | null>(null);
  const [calculatedEntry, setCalculatedEntry] = useState<CalculationIn | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);

  const [saved, setSaved] = useState<SavedCalculation[]>([]);
  const [savedPanel, setSavedPanel] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [savedNotice, setSavedNotice] = useState("");
  const readyForAutosave = useRef(false);
  const restoredWithMonth = useRef(false);

  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState("");
  const [ai, setAi] = useState<ExtractionOut | null>(null);
  const [importNotice, setImportNotice] = useState("");

  // drag and drop of documents (PDF/Excel/CSV); selections and drops ACCUMULATE (dedup by
  // name+size) and every file can be removed
  const acceptsFile = (f: File) => /\.(pdf|xlsx|csv)$/i.test(f.name) || f.type === "application/pdf";
  const addFiles = (incoming: File[]) => {
    setFiles((current) => {
      const keys = new Set(current.map((f) => `${f.name}|${f.size}`));
      return [...current, ...incoming.filter((f) => acceptsFile(f) && !keys.has(`${f.name}|${f.size}`))];
    });
  };
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  };

  // -- local persistence: snapshot and restore the whole form ------------------------
  const currentState = (): FormState => ({
    caseInfo,
    finalDate,
    adjustUntil,
    index,
    interestRegime,
    fixedRate,
    interestStart,
    fine523,
    fee523,
    pct523,
    penaltyOn,
    penaltyPct,
    penaltyBase,
    lateFineOn,
    lateFinePct,
    lateFineInFeeBase,
    deductions,
    entries,
    awardedOn,
    awardedPct,
    awardedBase,
    awardedIsClaim,
    contractOn,
    contractPct,
    titleOn,
    titlePct,
    titleOnFine,
    claimValue,
    claimValueMonth,
    installments,
  });

  const applyState = (s: FormState) => {
    setCaseInfo(s.caseInfo ?? { number: "", creditor: "", debtor: "" });
    setFinalDate(s.finalDate || today());
    setAdjustUntil(s.adjustUntil || previousMonth());
    setIndex(s.index || "tjdft");
    setInterestRegime(s.interestRegime || "legal");
    setFixedRate(s.fixedRate || "1,00");
    setInterestStart(s.interestStart || "");
    setFine523(!!s.fine523);
    setFee523(!!s.fee523);
    setPct523(s.pct523 || "10");
    setPenaltyOn(!!s.penaltyOn);
    setPenaltyPct(s.penaltyPct || "25");
    setPenaltyBase(s.penaltyBase || "gross");
    setLateFineOn(!!s.lateFineOn);
    setLateFinePct(s.lateFinePct || "10");
    setLateFineInFeeBase(!!s.lateFineInFeeBase);
    setDeductions(s.deductions ?? []);
    setEntries(s.entries ?? []);
    setAwardedOn(!!s.awardedOn);
    setAwardedPct(s.awardedPct || "10");
    setAwardedBase(s.awardedBase || "net");
    setAwardedIsClaim(!!s.awardedIsClaim);
    setContractOn(!!s.contractOn);
    setContractPct(s.contractPct || "30");
    setTitleOn(!!s.titleOn);
    setTitlePct(s.titlePct || "20");
    setTitleOnFine(!!s.titleOnFine);
    setClaimValue(s.claimValue || "");
    setClaimValueMonth(s.claimValueMonth || "");
    setInstallments(s.installments ?? []);
    setNewInstallment({ amount: "", on: "", description: "" });
    setNewDeduction({ description: "", amount: "" });
  };

  const saveCurrent = () => {
    try {
      setSaved(saveCalculation(saveName || caseInfo.number, currentState(), result?.totals.grand_total ?? null));
      setSaveName("");
      setSavedNotice("✓ Calculation saved in this browser");
      setTimeout(() => setSavedNotice(""), 2500);
    } catch (e) {
      setSavedNotice(e instanceof Error ? e.message : "Failed to save.");
    }
  };

  const openSaved = (s: SavedCalculation) => {
    applyState(s.state);
    setResult(null);
    setCalculatedEntry(null);
    setAi(null);
    setSavedPanel(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const newCalculation = () => {
    applyState(emptyState(latestPublished ?? previousMonth()));
    setResult(null);
    setCalculatedEntry(null);
    setAi(null);
    setFiles([]);
    clearDraft();
    setSavedPanel(false);
  };

  const loadSample = () => {
    applyState({ ...emptyState(latestPublished ?? previousMonth()), ...SAMPLE_CASE });
    setResult(null);
    setCalculatedEntry(null);
    setAi(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const signOut = async () => {
    await fetch("/api/sign-out", { method: "POST" }).catch(() => {});
    router.push("/sign-in");
  };

  const clearAll = () => {
    const hasContent = installments.length > 0 || result || deductions.length > 0;
    if (
      hasContent &&
      !window.confirm("Start a new calculation? This clears the current form. Saved calculations are not affected.")
    )
      return;
    newCalculation();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // restores the draft of the last visit and loads the saved list. Browser storage is only
  // readable after hydration, and the restore is deferred one tick so React commits the
  // server markup first instead of cascading renders inside the effect.
  useEffect(() => {
    const id = window.setTimeout(() => {
      const draft = readDraft();
      if (draft) {
        applyState(draft);
        if (draft.adjustUntil) restoredWithMonth.current = true;
      }
      setSaved(listSaved());
      readyForAutosave.current = true;
    }, 0);
    return () => window.clearTimeout(id);
  }, []);

  // draft autosave on every edit (light debounce)
  useEffect(() => {
    if (!readyForAutosave.current) return;
    const timer = setTimeout(() => saveDraft(currentState()), 600);
    return () => clearTimeout(timer);
  });

  const runExtraction = async () => {
    if (files.length === 0) return;
    setExtractionError("");
    setExtracting(true);
    try {
      const body = await extract(files);
      const e = body.extraction;
      setAi(body);
      // pre-fills the form; the lawyer reviews everything before calculating
      setCaseInfo({
        number: e.case_number.value ?? "",
        creditor: e.creditor.value ?? "",
        debtor: e.debtor.value ?? "",
      });
      setInstallments(e.installments.map((i) => ({ amount: i.amount, on: i.on, description: i.description })));
      setDeductions((e.deductions ?? []).map((d) => ({ description: d.description, amount: d.amount })));
      setEntries((e.entries ?? []).map((x) => ({ kind: x.kind, description: x.description, amount: x.amount, on: x.on })));
      if (e.index.value) setIndex(e.index.value);
      if (e.interest_regime.value) setInterestRegime(e.interest_regime.value as InterestRegime);
      if (e.interest_fixed_rate.value) setFixedRate(e.interest_fixed_rate.value.replace(".", ","));
      setInterestStart(e.interest_start.value ?? "");
      setFine523(e.fine_523_pct.value !== null);
      setFee523(e.fee_523_pct.value !== null);
      if (e.fine_523_pct.value ?? e.fee_523_pct.value) setPct523(e.fine_523_pct.value ?? e.fee_523_pct.value ?? "10");
      if (e.penalty_pct.value) {
        setPenaltyOn(true);
        setPenaltyPct(e.penalty_pct.value);
      }
      if (e.late_fine_pct?.value) {
        setLateFineOn(true);
        setLateFinePct(e.late_fine_pct.value);
      }
      if (e.title_fee_pct?.value) {
        setTitleOn(true);
        setTitlePct(e.title_fee_pct.value);
      }
      if (e.awarded_fee_pct.value) {
        setAwardedOn(true);
        setAwardedPct(e.awarded_fee_pct.value);
        if (e.awarded_fee_base.value === "claim_value") {
          setAwardedBase("claim_value");
          if (e.claim_value?.value) setClaimValue(formatAmountBR(e.claim_value.value.replace(".", ",")));
        }
      }
      setAwardedIsClaim(e.awarded_fees_are_the_claim?.value === "yes");
      setResult(null);
    } catch (err) {
      setExtractionError(err instanceof Error ? err.message : "Extraction failed.");
    } finally {
      setExtracting(false);
    }
  };

  useEffect(() => {
    latestMonths()
      .then((latest) => {
        const until = [latest["ipca"], latest["inpc"]].filter(Boolean).sort()[0];
        if (until) {
          setLatestPublished(until);
          // does not overwrite the month chosen on a previous visit (draft)
          if (!restoredWithMonth.current) setAdjustUntil(until);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (result) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result]);

  // the browser prints the page title in the header: neutralise it while printing (the
  // document goes into the court file)
  useEffect(() => {
    const original = document.title;
    const before = () => {
      document.title = "Calculation statement";
    };
    const after = () => {
      document.title = original;
    };
    window.addEventListener("beforeprint", before);
    window.addEventListener("afterprint", after);
    return () => {
      window.removeEventListener("beforeprint", before);
      window.removeEventListener("afterprint", after);
    };
  }, []);

  const nominalSum = installments.reduce((s, i) => s + Number(i.amount), 0);

  const addInstallment = () => {
    const amount = parseAmountBR(newInstallment.amount);
    if (!amount || !newInstallment.on) return;
    setInstallments((list) => [...list, { amount, on: newInstallment.on, description: newInstallment.description }]);
    setJustAdded(installments.length);
    setNewInstallment({ amount: "", on: "", description: "" });
  };

  const importSpreadsheet = async (file: File | undefined) => {
    if (!file) return;
    setImportNotice("");
    try {
      const imported = await importInstallments(file);
      setInstallments((current) => [...current, ...imported]);
      setImportNotice(`✓ ${imported.length} installment${imported.length > 1 ? "s" : ""} imported from ${file.name}; check dates and amounts`);
    } catch (e) {
      setImportNotice(e instanceof Error ? e.message : "Failed to read the spreadsheet.");
    }
  };

  const onEnter = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addInstallment();
    }
  };

  const run = async () => {
    setError("");
    setResult(null);
    // friendly validations BEFORE calling the API (they name the exact field)
    if (awardedOn && awardedBase === "claim_value" && !claimValue.trim()) {
      setError("Fees over the claim value require the “Claim value (R$)” field: enter it or change the base to “Net refund”.");
      return;
    }
    if (interestRegime === "fixed" && !fixedRate.trim()) {
      setError("The “Fixed percentage” interest regime requires the monthly rate.");
      return;
    }
    setLoading(true);
    try {
      const entry: CalculationIn = {
        final_date: finalDate,
        adjust_until: adjustUntil,
        index,
        interest: {
          regime: interestRegime,
          fixed_rate: interestRegime === "fixed" ? parsePct(fixedRate) : null,
          start: interestStart || null,
        },
        penalty: penaltyOn && penaltyPct ? { pct: parsePct(penaltyPct), base: penaltyBase } : null,
        deductions,
        awarded_fees:
          awardedOn && awardedPct
            ? {
                pct: parsePct(awardedPct),
                base: awardedBase,
                is_the_claim: awardedIsClaim,
                claim_value: awardedBase === "claim_value" ? parseAmountBR(claimValue) : null,
                claim_value_month: awardedBase === "claim_value" && claimValueMonth ? claimValueMonth : null,
              }
            : null,
        fine_523_pct: fine523 ? parsePct(pct523) : null,
        fee_523_pct: fee523 ? parsePct(pct523) : null,
        late_fine: lateFineOn && lateFinePct ? { pct: parsePct(lateFinePct), in_fee_base: lateFineInFeeBase } : null,
        contract_fee_pct: contractOn && contractPct ? parsePct(contractPct) : null,
        title_fees: titleOn && titlePct ? { pct: parsePct(titlePct), on_fine: titleOnFine } : null,
        entries,
        installments,
      };
      setResult(await calculate(entry));
      setCalculatedEntry(entry);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to call the calculation API.");
    } finally {
      setLoading(false);
    }
  };

  const downloadPdf = async () => {
    if (!result || !calculatedEntry) return;
    setGeneratingPdf(true);
    try {
      await downloadStatementPdf(calculatedEntry, caseInfo);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate the statement PDF.");
    } finally {
      setGeneratingPdf(false);
    }
  };

  const copySummary = async () => {
    if (!result) return;
    const t = result.totals;
    const lines = [
      `Update statement (${dateBR(result.parameters.final_date as string)})`,
      caseInfo.number && `Case: ${caseInfo.number}`,
      caseInfo.creditor && `${caseInfo.creditor} × ${caseInfo.debtor}`,
      `Adjusted until ${monthLabel(result.parameters.adjust_until as string)} · ${installments.length} amount(s)`,
      `Total original: ${brl(t.original)}`,
      `(+) Monetary adjustment: ${brl((Number(t.adjusted) - Number(t.original)).toFixed(2))}`,
      `(+) Default interest: ${brl(t.interest)}`,
      t.late_fine !== "0.00" && `(+) Late fine: ${brl(t.late_fine)}`,
      `Gross total (A): ${brl(t.gross_total_A)}`,
      t.fees_and_expenses !== "0.00" && `(+) Adjusted court fees/expenses: ${brl(t.fees_and_expenses)}`,
      t.discounts !== "0.00" && `(−) Adjusted discounts/abatements: ${brl(t.discounts)}`,
      t.fine_523_B !== "0.00" && `(+) Fine, CPC art. 523 (B): ${brl(t.fine_523_B)}`,
      t.fee_523_C !== "0.00" && `(+) Fees, CPC art. 523 (C): ${brl(t.fee_523_C)}`,
      `GRAND TOTAL: ${brl(t.grand_total)}`,
    ].filter(Boolean);
    await navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const calculateButton = (classes: string) => (
    <button
      onClick={run}
      disabled={loading || installments.length === 0}
      className={`rounded-md bg-accent font-bold uppercase tracking-wide text-white transition-all hover:opacity-90 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 ${classes}`}
    >
      {loading ? (
        <span className="inline-flex items-center gap-2">
          <Spinner />
          Calculating…
        </span>
      ) : (
        "Calculate"
      )}
    </button>
  );

  const pctInput = (value: string, onChange: (v: string) => void, width = "w-20") => (
    <input
      className={`${width} rounded-md border border-line px-3 py-1.5 text-center text-sm outline-none transition-colors focus:border-accent`}
      inputMode="decimal"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );

  return (
    <>
      <header className="no-print sticky top-0 z-40 border-b border-line bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2.5 sm:px-6">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/mark.svg" alt="" className="h-8 w-8" />
            <div>
              <p className="text-base font-bold leading-tight text-ink sm:text-lg">Court Debt Calculator</p>
              <p className="hidden text-[9px] uppercase tracking-widest text-muted sm:block">
                the model interprets · the engine computes
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              type="button"
              onClick={loadSample}
              title="Fills the form with reference case 01, validated to the cent against a public court calculator"
              className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-muted transition-colors hover:border-accent hover:text-accent"
            >
              Load sample case
            </button>
            {(installments.length > 0 || deductions.length > 0 || result) && (
              <button
                type="button"
                onClick={clearAll}
                className="hidden rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-muted transition-colors hover:border-red-400 hover:text-red-600 sm:inline-flex"
              >
                Clear all
              </button>
            )}
            <div className="relative">
              <button
                type="button"
                onClick={() => setSavedPanel(!savedPanel)}
                className={`rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors ${
                  savedPanel ? "border-accent bg-accent-soft text-ink" : "border-line text-muted hover:border-ink hover:text-ink"
                }`}
              >
                🗂 Saved{saved.length > 0 ? ` (${saved.length})` : ""}
              </button>
              {savedPanel && (
                <div className="animate-enter absolute right-0 top-full z-50 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-line bg-white p-3 shadow-lg">
                  <p className="mb-2 text-[11px] font-bold uppercase tracking-wide text-ink">Calculations saved in this browser</p>
                  <div className="mb-2 flex gap-2">
                    <input
                      className="field px-2.5 py-1.5 text-xs"
                      placeholder="Name (e.g. the case number)"
                      value={saveName}
                      onChange={(e) => setSaveName(e.target.value)}
                    />
                    <button
                      onClick={saveCurrent}
                      disabled={installments.length === 0}
                      className="shrink-0 rounded-md bg-ink px-3 py-1.5 text-xs font-semibold text-white transition-all hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Save
                    </button>
                  </div>
                  {savedNotice && (
                    <p className={`mb-2 text-[11px] ${savedNotice.startsWith("✓") ? "text-emerald-700" : "text-red-600"}`}>{savedNotice}</p>
                  )}
                  {saved.length === 0 ? (
                    <p className="py-2 text-xs text-muted">Nothing saved yet: fill the form and save it with a name.</p>
                  ) : (
                    <ul className="max-h-72 space-y-1.5 overflow-y-auto">
                      {saved.map((s) => (
                        <li key={s.id} className="rounded-md border border-line bg-surface/60 px-2.5 py-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <div className="min-w-0">
                              <p className="truncate text-xs font-semibold text-ink">{s.name}</p>
                              <p className="text-[10px] text-muted">
                                {new Date(s.createdAt).toLocaleDateString("en-GB")} · {s.state.installments.length} amount
                                {s.state.installments.length === 1 ? "" : "s"}
                                {s.grandTotal ? ` · ${brl(s.grandTotal)}` : ""}
                              </p>
                            </div>
                            <div className="flex shrink-0 items-center gap-1">
                              <button
                                onClick={() => openSaved(s)}
                                className="rounded border border-ink px-2 py-0.5 text-[10px] font-semibold text-ink transition-colors hover:bg-ink hover:text-white"
                              >
                                Open
                              </button>
                              <button
                                onClick={() => setSaved(deleteCalculation(s.id))}
                                className="rounded px-1.5 py-0.5 text-xs text-red-400 transition-colors hover:bg-red-50"
                                aria-label={`delete ${s.name}`}
                              >
                                ✕
                              </button>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                  <button
                    onClick={newCalculation}
                    className="mt-3 w-full rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-muted transition-colors hover:border-accent hover:text-accent"
                  >
                    Clear the form (new calculation)
                  </button>
                  <p className="mt-2 text-[10px] leading-snug text-muted">Calculations are kept only in this browser/machine.</p>
                </div>
              )}
            </div>
            {PASSWORD_GATE && (
              <button
                type="button"
                onClick={signOut}
                title="End the session and return to the sign-in screen"
                className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-muted transition-colors hover:border-red-400 hover:text-red-600"
              >
                Sign out
              </button>
            )}
          </div>
        </div>
        <div className="h-1 bg-line">
          <div className="h-full w-24 bg-accent" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 pb-28 pt-6 sm:px-6 sm:pb-10 xl:px-10">
        <div className="no-print">
          <Card
            title="Extraction from documents (beta)"
            extra={
              ai && (
                <span
                  className={`rounded-full px-3 py-1 text-[11px] font-semibold ${
                    ai.simulated ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
                  }`}
                >
                  {ai.simulated ? "simulated mode (no API key)" : `extracted · ${ai.model}`}
                </span>
              )
            }
          >
            <p className="mb-3 text-xs text-muted">
              Attach the case documents, <strong>PDF (scanned included) or an Excel/CSV spreadsheet</strong>: judgment,
              appellate decision, settlement approval, payment history, contract… The model classifies each document,
              applies the hierarchy (the most recent decision prevails; an appellate decision reverses the judgment; an
              approved settlement governs the calculation) and pre-fills the form below for your review. What the
              documents do not state is flagged “not identified”. <strong>No document is stored.</strong>
            </p>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setDragging(false);
              }}
              onDrop={onDrop}
              className={`flex flex-wrap items-center gap-3 rounded-md transition-colors ${dragging ? "bg-accent-soft ring-2 ring-accent ring-offset-2" : ""}`}
            >
              <label className="cursor-pointer rounded-md border border-dashed border-line px-4 py-2 text-sm text-muted transition-colors hover:border-accent hover:text-accent">
                {files.length === 0
                  ? dragging
                    ? "Drop the files here"
                    : "+ Select or drop files (PDF/Excel)"
                  : `${files.length} file${files.length > 1 ? "s" : ""} selected`}
                <input
                  type="file"
                  accept="application/pdf,.xlsx,.csv"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    addFiles(Array.from(e.target.files ?? []));
                    e.target.value = ""; // allows re-selecting the same file
                  }}
                />
              </label>
              {files.map((f, i) => (
                <span key={`${f.name}|${f.size}`} className="flex max-w-xs items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-xs text-muted">
                  <span className="truncate">{f.name}</span>
                  <button
                    type="button"
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                    aria-label={`remove ${f.name}`}
                    className="shrink-0 rounded-full px-1 text-red-400 transition-colors hover:bg-red-50 hover:text-red-600"
                  >
                    ✕
                  </button>
                </span>
              ))}
              <button
                onClick={runExtraction}
                disabled={extracting || files.length === 0}
                className="rounded-md bg-ink px-5 py-2 text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {extracting ? (
                  <span className="inline-flex items-center gap-2">
                    <Spinner />
                    Reading the documents…
                  </span>
                ) : (
                  "⚡ Extract parameters"
                )}
              </button>
            </div>
            {extractionError && (
              <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{extractionError}</p>
            )}
            {ai && ai.extraction.settlement?.value && (
              <div
                className="animate-enter mt-3 rounded-md border-2 border-accent bg-accent-soft px-3 py-2 text-xs leading-relaxed text-ink"
                title={ai.extraction.settlement.quote ? `Excerpt of the document: “${ai.extraction.settlement.quote}”` : undefined}
              >
                <strong>⚠ Approved settlement identified.</strong> Its terms prevail over the merits and become the base of the
                calculation: {ai.extraction.settlement.value}
              </div>
            )}
            {ai && ai.extraction.documents?.length > 0 && (
              <div className="animate-enter mt-3 rounded-md border border-line bg-surface px-3 py-2 text-xs leading-relaxed">
                <strong className="text-ink">Recognised documents:</strong>
                <ul className="mt-1 space-y-0.5">
                  {ai.extraction.documents.map((d, i) => (
                    <li key={i} className="text-muted">
                      📄 <span className="font-semibold">{d.kind}</span>
                      {d.on && ` · ${dateBR(d.on)}`}
                      <span className="text-muted/70"> · {d.file_name}</span>
                      {d.role && <span> · {d.role}</span>}
                    </li>
                  ))}
                </ul>
                {ai.extraction.prevailing_decision?.value && (
                  <p className="mt-1.5 border-t border-line pt-1.5 text-muted">
                    <strong className="text-ink">Decision governing the calculation:</strong> {ai.extraction.prevailing_decision.value}
                    <AiBadge field={ai.extraction.prevailing_decision} />
                  </p>
                )}
              </div>
            )}
            {ai && (
              <div className="animate-enter mt-3 rounded-md border border-line bg-surface px-3 py-2 text-xs leading-relaxed text-muted">
                <strong className="text-ink">Extraction notes:</strong> {ai.extraction.notes}{" "}
                <span className="text-muted/70">Hover the “⚡ AI” badges to see the excerpt that supports each field.</span>
              </div>
            )}
          </Card>

          <Card title="Case (optional)">
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label className={labelClass}>
                  Case number
                  <AiBadge field={ai?.extraction.case_number} />
                </label>
                <input
                  className="field"
                  placeholder="0000000-00.0000.0.00.0000"
                  value={caseInfo.number}
                  onChange={(e) => setCaseInfo({ ...caseInfo, number: e.target.value })}
                />
              </div>
              <div>
                <label className={labelClass}>
                  Creditor
                  <AiBadge field={ai?.extraction.creditor} />
                </label>
                <input className="field" value={caseInfo.creditor} onChange={(e) => setCaseInfo({ ...caseInfo, creditor: e.target.value })} />
              </div>
              <div>
                <label className={labelClass}>
                  Debtor
                  <AiBadge field={ai?.extraction.debtor} />
                </label>
                <input className="field" value={caseInfo.debtor} onChange={(e) => setCaseInfo({ ...caseInfo, debtor: e.target.value })} />
              </div>
            </div>
          </Card>

          <Card
            title="Amounts"
            extra={
              installments.length > 0 && (
                <span className="rounded-full bg-ink px-3 py-1 text-[11px] font-semibold text-white">
                  {installments.length} amount{installments.length > 1 ? "s" : ""} · {brl(nominalSum.toFixed(2))}
                </span>
              )
            }
          >
            <div className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_2fr_auto]">
              <div>
                <label className={labelClass}>Amount (R$)</label>
                <input
                  className="field"
                  inputMode="decimal"
                  placeholder="1.850,00"
                  value={newInstallment.amount}
                  onChange={(e) => setNewInstallment({ ...newInstallment, amount: formatAmountBR(e.target.value) })}
                  onKeyDown={onEnter}
                />
              </div>
              <div>
                <label className={labelClass}>Date of the amount</label>
                <DatePicker testid="amount-date" value={newInstallment.on} onChange={(d) => setNewInstallment({ ...newInstallment, on: d })} />
              </div>
              <div>
                <label className={labelClass}>Description</label>
                <input
                  className="field"
                  placeholder="Installment 1"
                  value={newInstallment.description}
                  onChange={(e) => setNewInstallment({ ...newInstallment, description: e.target.value })}
                  onKeyDown={onEnter}
                />
              </div>
              <button onClick={addInstallment} className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]">
                + Add
              </button>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <label className="cursor-pointer rounded-md border border-dashed border-line px-3 py-1.5 text-xs font-semibold text-muted transition-colors hover:border-accent hover:text-accent">
                📄 Import a spreadsheet (Excel/CSV)
                <input
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  className="hidden"
                  onChange={(e) => {
                    importSpreadsheet(e.target.files?.[0]);
                    e.target.value = "";
                  }}
                />
              </label>
              {importNotice && (
                <span className={`text-xs ${importNotice.startsWith("✓") ? "text-emerald-700" : "text-red-600"}`}>{importNotice}</span>
              )}
            </div>
            <p className="mt-1.5 text-[11px] text-muted">
              tip: Enter adds the amount and keeps the focus for the next one
              {ai && ai.extraction.installments.length > 0 && (
                <span className="ml-2 font-semibold text-amber-600">· amounts pre-filled by the model: check dates and amounts before calculating</span>
              )}
            </p>

            {installments.length > 0 && (
              <>
                <div className="mt-3 hidden sm:block">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
                        <th className="px-2 py-1">#</th>
                        <th className="px-2">Date</th>
                        <th className="px-2 text-right">Amount</th>
                        <th className="px-4">Description</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {installments.map((i, n) => (
                        <tr key={`${i.on}-${n}`} className={`border-b border-line/60 ${n === justAdded ? "animate-highlight" : ""}`}>
                          <td className="px-2 py-1.5 text-muted">{n + 1}</td>
                          <td className="px-2">{dateBR(i.on)}</td>
                          <td className="px-2 text-right tabular-nums">{brl(i.amount)}</td>
                          <td className="px-4 text-muted">{i.description}</td>
                          <td className="text-right">
                            <button
                              onClick={() => setInstallments(installments.filter((_, j) => j !== n))}
                              className="rounded px-2 py-0.5 text-xs text-red-500 transition-colors hover:bg-red-50"
                            >
                              remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <ul className="mt-3 space-y-2 sm:hidden">
                  {installments.map((i, n) => (
                    <li key={`${i.on}-${n}`} className={`flex items-center justify-between rounded-md border border-line px-3 py-2 ${n === justAdded ? "animate-highlight" : ""}`}>
                      <div>
                        <p className="text-sm font-semibold tabular-nums text-ink">{brl(i.amount)}</p>
                        <p className="text-[11px] text-muted">
                          {dateBR(i.on)}
                          {i.description && ` · ${i.description}`}
                        </p>
                      </div>
                      <button onClick={() => setInstallments(installments.filter((_, j) => j !== n))} className="rounded p-1.5 text-red-400 transition-colors hover:bg-red-50" aria-label="remove">
                        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
                          <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>

          <Card title="Monetary adjustment">
            <div className="mb-3">
              <label className={labelClass}>
                Index
                <AiBadge field={ai?.extraction.index} />
              </label>
              <Pills
                value={index}
                onChange={setIndex}
                options={[
                  { v: "tjdft", title: "INPC → IPCA", detail: "IPCA from 09/2024 · Law 14,905" },
                  { v: "tjsp", title: "TJSP table", detail: "INPC → IPCA-15 from 08/2024" },
                  { v: "inpc", title: "INPC", detail: "whole period" },
                  { v: "ipca", title: "IPCA", detail: "whole period" },
                  { v: "ipca15", title: "IPCA-15", detail: "whole period" },
                  { v: "igpm", title: "IGP-M", detail: "whole period" },
                  { v: "igpdi", title: "IGP-DI", detail: "whole period" },
                ]}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className={labelClass}>Adjusted until (month)</label>
                <MonthPicker value={adjustUntil} onChange={setAdjustUntil} maximum={latestPublished} maximumLabel="latest published" />
                <p className="mt-1 text-[11px] text-muted">months not yet published by IBGE / the central bank are blocked</p>
              </div>
              <div>
                <label className={labelClass}>Final date of the calculation</label>
                <DatePicker testid="final-date" value={finalDate} onChange={setFinalDate} />
                <p className="mt-1 text-[11px] text-muted">end of the interest count</p>
              </div>
            </div>
          </Card>

          <Card title="Default interest">
            <div className="mb-3">
              <label className={labelClass}>
                Regime
                <AiBadge field={ai?.extraction.interest_regime} />
              </label>
              <Pills
                value={interestRegime}
                onChange={(v) => setInterestRegime(v)}
                options={[
                  { v: "legal", title: "Legal interest", detail: "1% per month → Legal Rate on 30/08/2024" },
                  { v: "legal_rate", title: "Legal Rate", detail: "whole period (SGS 29543)" },
                  { v: "fixed", title: "Fixed percentage", detail: "full calendar months" },
                  { v: "none", title: "No interest", detail: "adjustment only" },
                ]}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {interestRegime === "fixed" && (
                <div>
                  <label className={labelClass}>Rate (% per month)</label>
                  <input className="field" inputMode="decimal" value={fixedRate} onChange={(e) => setFixedRate(e.target.value)} />
                </div>
              )}
              {interestRegime !== "none" && (
                <div>
                  <label className={labelClass}>
                    Start (service of process, final judgment…)
                    <AiBadge field={ai?.extraction.interest_start} />
                  </label>
                  <DatePicker testid="interest-start" value={interestStart} onChange={setInterestStart} clearable />
                  <p className="mt-1 text-[11px] text-muted">empty = from each amount&apos;s date</p>
                </div>
              )}
            </div>
          </Card>

          <Card title="Late / contractual fine (adds to the debt)">
            <div className="flex flex-wrap items-center gap-3">
              <Toggle on={lateFineOn} onClick={() => setLateFineOn(!lateFineOn)}>
                Fine of
              </Toggle>
              {pctInput(lateFinePct, setLateFinePct)}
              <span className="text-sm text-muted">% over each installment&apos;s adjusted amount</span>
              <AiBadge field={ai?.extraction.late_fine_pct} />
            </div>
            <p className="mt-1 text-[11px] text-muted">
              a fine that ADDS to the debt (e.g. a contract clause, Civil Code art. 1,336 §1); not the contractual penalty (which
              deducts) nor the art. 523 fine
            </p>
            {lateFineOn && (
              <label className="mt-3 flex items-center gap-2 text-sm text-muted">
                <input type="checkbox" className="h-4 w-4 accent-[#047857]" checked={lateFineInFeeBase} onChange={(e) => setLateFineInFeeBase(e.target.checked)} />
                the awarded fees also accrue on the fine
                <span className="text-[11px] text-muted/70">(unchecked = “not applicable over the fine”)</span>
              </label>
            )}
          </Card>

          <Card title="Deductions and abatements">
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <Toggle on={penaltyOn} onClick={() => setPenaltyOn(!penaltyOn)}>
                Contractual penalty of
              </Toggle>
              {pctInput(penaltyPct, setPenaltyPct)}
              <span className="text-sm text-muted">%</span>
              <AiBadge field={ai?.extraction.penalty_pct} />
            </div>
            {penaltyOn && (
              <div className="mb-4">
                <label className={labelClass}>Base of the penalty</label>
                <Pills
                  columns="grid-cols-3"
                  value={penaltyBase}
                  onChange={(v) => setPenaltyBase(v)}
                  options={[
                    { v: "gross", title: "Gross", detail: "adjusted + interest" },
                    { v: "adjusted", title: "Adjusted", detail: "no interest" },
                    { v: "nominal", title: "Nominal", detail: "amounts paid" },
                  ]}
                />
              </div>
            )}

            <label className={labelClass}>Deductions by amount, of any nature (partial payment, usage fee, condominium charges, brokerage, abatement…)</label>
            <div className="grid items-end gap-3 sm:grid-cols-[2fr_1fr_auto]">
              <input
                className="field"
                placeholder="Description, e.g. Partial payment of 10/2025"
                value={newDeduction.description}
                onChange={(e) => setNewDeduction({ ...newDeduction, description: e.target.value })}
              />
              <input
                className="field"
                inputMode="decimal"
                placeholder="1.097,66"
                value={newDeduction.amount}
                onChange={(e) => setNewDeduction({ ...newDeduction, amount: formatAmountBR(e.target.value) })}
              />
              <button
                onClick={() => {
                  const amount = parseAmountBR(newDeduction.amount);
                  if (!newDeduction.description || !amount) return;
                  setDeductions((d) => [...d, { description: newDeduction.description, amount }]);
                  setNewDeduction({ description: "", amount: "" });
                }}
                className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]"
              >
                + Add
              </button>
            </div>
            {deductions.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {deductions.map((d, i) => (
                  <li key={i} className="flex items-center justify-between rounded-md border border-line bg-surface/60 px-3 py-1.5 text-sm">
                    <span className="text-muted">{d.description}</span>
                    <span className="flex items-center gap-3">
                      <span className="tabular-nums text-red-600">− {brl(d.amount)}</span>
                      <button onClick={() => setDeductions(deductions.filter((_, j) => j !== i))} className="rounded px-1.5 text-xs text-red-400 transition-colors hover:bg-red-50">
                        ✕
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {ai?.extraction.deductions_mentioned && (
              <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-800">
                <strong>⚡ The decision mentions deductions still to be assessed:</strong> {ai.extraction.deductions_mentioned}. Enter the
                assessed amounts above.
              </p>
            )}
          </Card>

          <Card title="Court fees, expenses and abatements (dated)">
            <p className="mb-3 text-xs text-muted">
              Entries <strong>adjusted by the calculation&apos;s index from their own date</strong>, without interest: court fees and
              procedural expenses <strong>add</strong> to the amount; discounts/abatements (e.g. a recognised partial payment){" "}
              <strong>subtract</strong> by their adjusted amount.
            </p>
            <div className="grid items-end gap-3 sm:grid-cols-[1fr_2fr_1fr_1fr_auto]">
              <div>
                <label className={labelClass}>Kind</label>
                <select className="field" value={newEntry.kind} onChange={(e) => setNewEntry({ ...newEntry, kind: e.target.value as EntryKind })}>
                  <option value="court_fee">Court fee</option>
                  <option value="expense">Procedural expense</option>
                  <option value="discount">Discount / abatement</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Description</label>
                <input className="field" placeholder="Initial court fees, partial payment…" value={newEntry.description} onChange={(e) => setNewEntry({ ...newEntry, description: e.target.value })} />
              </div>
              <div>
                <label className={labelClass}>Amount (R$)</label>
                <input className="field" inputMode="decimal" placeholder="500,00" value={newEntry.amount} onChange={(e) => setNewEntry({ ...newEntry, amount: formatAmountBR(e.target.value) })} />
              </div>
              <div>
                <label className={labelClass}>Date</label>
                <DatePicker testid="entry-date" value={newEntry.on} onChange={(d) => setNewEntry({ ...newEntry, on: d })} />
              </div>
              <button
                onClick={() => {
                  const amount = parseAmountBR(newEntry.amount);
                  if (!amount || !newEntry.on) return;
                  setEntries((list) => [...list, { ...newEntry, amount }]);
                  setNewEntry({ kind: newEntry.kind, description: "", amount: "", on: "" });
                }}
                className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]"
              >
                + Add
              </button>
            </div>
            {entries.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {entries.map((x, i) => (
                  <li key={i} className="flex items-center justify-between rounded-md border border-line bg-surface/60 px-3 py-1.5 text-sm">
                    <span className="text-muted">
                      <span className="font-semibold text-ink">{ENTRY_LABELS[x.kind]}</span>
                      {x.description && ` · ${x.description}`} · {dateBR(x.on)}
                    </span>
                    <span className="flex items-center gap-3">
                      <span className={`tabular-nums ${x.kind === "discount" ? "text-red-600" : "text-emerald-700"}`}>
                        {x.kind === "discount" ? "− " : "+ "}
                        {brl(x.amount)}
                      </span>
                      <button onClick={() => setEntries(entries.filter((_, j) => j !== i))} className="rounded px-1.5 text-xs text-red-400 transition-colors hover:bg-red-50">
                        ✕
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Attorney fees">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <Toggle on={awardedOn} onClick={() => setAwardedOn(!awardedOn)}>
                Awarded fees of
              </Toggle>
              {pctInput(awardedPct, setAwardedPct)}
              <span className="text-sm text-muted">% (CPC art. 85)</span>
              <AiBadge field={ai?.extraction.awarded_fee_pct} />
            </div>
            {awardedOn && (
              <>
                <div className="mb-3">
                  <label className={labelClass}>
                    Base
                    <AiBadge field={ai?.extraction.awarded_fee_base} />
                  </label>
                  <Pills
                    columns="grid-cols-2"
                    value={awardedBase}
                    onChange={(v) => setAwardedBase(v)}
                    options={[
                      { v: "net", title: "Net refund", detail: "the award after deductions" },
                      { v: "claim_value", title: "Claim value", detail: "nominal or adjusted" },
                    ]}
                  />
                </div>
                {awardedBase === "claim_value" && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <label className={labelClass}>Claim value (R$)</label>
                      <input className="field" inputMode="decimal" placeholder="48.990,00" value={claimValue} onChange={(e) => setClaimValue(formatAmountBR(e.target.value))} />
                    </div>
                    <div>
                      <label className={labelClass}>Adjust from (month)</label>
                      <MonthPicker value={claimValueMonth} onChange={setClaimValueMonth} maximum={latestPublished} maximumLabel="latest published" />
                      <p className="mt-1 text-[11px] text-muted">
                        empty = nominal value{" "}
                        {claimValueMonth && (
                          <button className="font-semibold text-accent hover:underline" onClick={() => setClaimValueMonth("")}>
                            · use nominal
                          </button>
                        )}
                      </p>
                    </div>
                  </div>
                )}
                <label className="mt-4 flex cursor-pointer items-start gap-2 rounded-md border border-line bg-surface/60 px-3 py-2.5 text-xs leading-relaxed text-muted">
                  <input type="checkbox" checked={awardedIsClaim} onChange={(e) => setAwardedIsClaim(e.target.checked)} className="mt-0.5 accent-[#047857]" />
                  <span>
                    <strong className="text-ink">The fees are the claim being enforced</strong> (enforcement of fees only): the amounts
                    above become just the <em>base of the calculation</em>; the enforced debt is the fees, and the art. 523 fine and
                    fees accrue on them.
                    <AiBadge field={ai?.extraction.awarded_fees_are_the_claim} />
                  </span>
                </label>
              </>
            )}

            <div className="mt-4 border-t border-line pt-4">
              <div className="flex flex-wrap items-center gap-3">
                <Toggle on={titleOn} onClick={() => setTitleOn(!titleOn)}>
                  Title fees of
                </Toggle>
                {pctInput(titlePct, setTitlePct)}
                <span className="text-sm text-muted">% over the net debt</span>
                <AiBadge field={ai?.extraction.title_fee_pct} />
              </div>
              <p className="mt-1 text-[11px] text-muted">
                provided for in the TITLE itself being enforced, with the debtor&apos;s consent (e.g. a debt-acknowledgement clause):{" "}
                <strong>they add to the debt</strong> and are cumulative with the fees awarded in a decision.
              </p>
              {titleOn && (
                <label className="mt-2 flex items-center gap-2 text-sm text-muted">
                  <input type="checkbox" className="h-4 w-4 accent-[#047857]" checked={titleOnFine} onChange={(e) => setTitleOnFine(e.target.checked)} />
                  they accrue on the debt WITH the late fine
                  <span className="text-[11px] text-muted/70">(clauses “over the total amount of the debt”)</span>
                </label>
              )}
            </div>

            <div className="mt-4 border-t border-line pt-4">
              <div className="flex flex-wrap items-center gap-3">
                <Toggle on={contractOn} onClick={() => setContractOn(!contractOn)}>
                  Contract fees of
                </Toggle>
                {pctInput(contractPct, setContractPct)}
                <span className="text-sm text-muted">% over the creditor&apos;s amount</span>
              </div>
              <p className="mt-1 text-[11px] text-muted">
                an <strong>informative</strong> line of the statement (how much the creditor&apos;s own lawyer withholds by contract): it
                is not part of the debt collected from the debtor. Fill it only when the information should appear in the document.
              </p>
            </div>
          </Card>

          <Card title="Enforcement of the judgment (CPC art. 523, §1)">
            <div className="flex flex-wrap items-center gap-3">
              <Toggle on={fine523} onClick={() => setFine523(!fine523)}>
                Fine
              </Toggle>
              <Toggle on={fee523} onClick={() => setFee523(!fee523)}>
                Fees
              </Toggle>
              <div className="flex items-center gap-2">
                {pctInput(pct523, setPct523, "w-16")}
                <span className="text-sm text-muted">% over the enforceable amount</span>
                <AiBadge field={ai?.extraction.fine_523_pct} />
              </div>
            </div>
          </Card>

          {error && (
            <div className="animate-enter mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <strong>The calculation could not proceed:</strong> {error}
            </div>
          )}

          <div className="hidden items-center gap-3 sm:flex">
            {calculateButton("px-10 py-3 text-sm")}
            {installments.length === 0 && <span className="text-xs text-muted">add at least one amount</span>}
          </div>
        </div>

        {result && (
          <div ref={resultRef} className="animate-enter mt-8 scroll-mt-20">
            <div className="rounded-lg border border-line bg-white p-4 shadow-sm sm:p-6">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3 border-b-2 border-accent pb-3">
                <div>
                  <h2 className="text-lg font-bold leading-tight text-ink">Calculation statement</h2>
                  <p className="text-xs text-muted">
                    {caseInfo.number && <>Case {caseInfo.number} · </>}
                    {caseInfo.creditor && (
                      <>
                        {caseInfo.creditor} × {caseInfo.debtor} ·{" "}
                      </>
                    )}
                    adjusted until {monthLabel(result.parameters.adjust_until as string)} · final date{" "}
                    {dateBR(result.parameters.final_date as string)}
                  </p>
                </div>
                <div className="no-print flex flex-wrap gap-2">
                  <button onClick={copySummary} className="rounded-md border border-line px-3 py-2 text-xs font-semibold text-muted transition-colors hover:border-ink hover:text-ink">
                    {copied ? "✓ Copied" : "Copy summary"}
                  </button>
                  <button onClick={() => exportExcel(result, caseInfo)} className="rounded-md border border-emerald-700 px-3 py-2 text-xs font-semibold text-emerald-700 transition-colors hover:bg-emerald-700 hover:text-white">
                    ⬇ Excel
                  </button>
                  <button
                    onClick={downloadPdf}
                    disabled={generatingPdf}
                    className="rounded-md border border-accent px-3 py-2 text-xs font-semibold text-accent transition-colors hover:bg-accent hover:text-white disabled:cursor-wait disabled:opacity-50"
                  >
                    {generatingPdf ? "Generating…" : "⬇ PDF"}
                  </button>
                  <button onClick={() => window.print()} className="rounded-md border border-ink px-3 py-2 text-xs font-semibold text-ink transition-colors hover:bg-ink hover:text-white">
                    Print
                  </button>
                  <button onClick={clearAll} className="rounded-md bg-ink px-3 py-2 text-xs font-semibold text-white transition-colors hover:opacity-90">
                    + New calculation
                  </button>
                </div>
              </div>

              <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="bg-ink text-left text-[11px] uppercase tracking-wide text-white">
                      <th className="rounded-l-md px-2 py-2">Date</th>
                      <th className="px-2">Description</th>
                      <th className="px-2 text-right">Original</th>
                      <th className="px-2 text-right">Factor</th>
                      <th className="px-2 text-right">Adjusted</th>
                      <th className="px-2 text-right">Interest %</th>
                      <th className="px-2 text-right">Interest</th>
                      {result.totals.late_fine !== "0.00" && <th className="px-2 text-right">Late fine</th>}
                      <th className="rounded-r-md px-2 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.lines.map((l, i) => (
                      <tr key={i} className={`border-b border-line/60 ${i % 2 ? "bg-surface/60" : ""}`}>
                        <td className="whitespace-nowrap px-2 py-1.5">{dateBR(l.on)}</td>
                        <td className="px-2 text-muted">{l.description}</td>
                        <td className="whitespace-nowrap px-2 text-right tabular-nums">{brl(l.amount)}</td>
                        <td className="px-2 text-right tabular-nums text-muted">{Number(l.factor).toFixed(6)}</td>
                        <td className="whitespace-nowrap px-2 text-right tabular-nums">{brl(l.adjusted)}</td>
                        <td className="px-2 text-right tabular-nums text-muted">{Number(l.interest_pct).toFixed(6)}%</td>
                        <td className="whitespace-nowrap px-2 text-right tabular-nums">{brl(l.interest)}</td>
                        {result.totals.late_fine !== "0.00" && <td className="whitespace-nowrap px-2 text-right tabular-nums">{brl(l.late_fine)}</td>}
                        <td className="whitespace-nowrap px-2 text-right font-semibold tabular-nums text-ink">{brl(l.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-accent-soft font-semibold text-ink">
                      <td className="rounded-l-md px-2 py-1.5" colSpan={2}>
                        TOTALS
                      </td>
                      <td className="whitespace-nowrap px-2 text-right tabular-nums">{brl(result.totals.original)}</td>
                      <td className="px-2" />
                      <td className="whitespace-nowrap px-2 text-right tabular-nums">{brl(result.totals.adjusted)}</td>
                      <td className="px-2" />
                      <td className="whitespace-nowrap px-2 text-right tabular-nums">{brl(result.totals.interest)}</td>
                      {result.totals.late_fine !== "0.00" && <td className="whitespace-nowrap px-2 text-right tabular-nums">{brl(result.totals.late_fine)}</td>}
                      <td className="whitespace-nowrap rounded-r-md px-2 text-right tabular-nums">{brl(result.totals.gross_total_A)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              <div className="mt-1 w-full space-y-1 text-sm">
                {(() => {
                  const t = result.totals;
                  const p = result.parameters;
                  const hasDeductions = t.total_deductions !== "0.00";
                  const hasFine = t.late_fine !== "0.00";
                  const line = (label: string, value: string, opts: { negative?: boolean; strong?: boolean; highlight?: boolean } = {}) => (
                    <div key={label} className={`flex justify-between py-1 ${opts.strong ? "-mx-2 rounded-md bg-accent-soft px-2 font-semibold text-ink" : "border-b border-line/60"}`}>
                      <span className={opts.strong ? "" : "text-muted"}>{label}</span>
                      <span className={`tabular-nums ${opts.negative ? "text-red-600" : ""} ${opts.highlight ? "font-bold text-accent" : ""}`}>
                        {opts.negative ? "− " : ""}
                        {brl(value)}
                      </span>
                    </div>
                  );
                  const note = creditorAmountNote(t, p);
                  return (
                    <>
                      {t.penalty !== "0.00" &&
                        line(
                          `(−) Contractual penalty ${p.penalty_pct}% (${{ gross: "on gross", adjusted: "on adjusted", nominal: "on nominal" }[p.penalty_base as string] ?? ""})`,
                          t.penalty,
                          { negative: true }
                        )}
                      {result.deductions.map((d) => line(`(−) ${d.description}`, d.amount, { negative: true }))}
                      {hasDeductions && line("= Net refund", t.net_amount, { strong: true })}
                      {t.awarded_fees !== "0.00" &&
                        line(
                          p.awarded_fees_are_the_claim
                            ? `(=) Enforced fees ${p.awarded_fee_pct}%: the claim being enforced (the base above is not part of the debt)`
                            : `(+) Awarded fees ${p.awarded_fee_pct}%${t.adjusted_claim_value ? ` (adjusted claim value ${brl(t.adjusted_claim_value)})` : ""}${
                                hasFine && !p.late_fine_in_fee_base ? ", base without the fine" : ""
                              }`,
                          t.awarded_fees,
                          { strong: !!p.awarded_fees_are_the_claim }
                        )}
                      {t.title_fees !== "0.00" &&
                        line(
                          `(+) Title fees ${p.title_fee_pct}%${p.title_fee_on_fine ? " (over the debt with the fine)" : hasFine ? ", base without the fine" : ""}`,
                          t.title_fees
                        )}
                      {result.entries?.map((x) =>
                        line(
                          `(${x.kind === "discount" ? "−" : "+"}) ${ENTRY_LABELS[x.kind]}${x.description ? `: ${x.description}` : ""} (${dateBR(x.on)}, adjusted)`,
                          x.adjusted,
                          { negative: x.kind === "discount" }
                        )
                      )}
                      {t.enforceable_amount !== t.gross_total_A && line("= Enforceable amount", t.enforceable_amount, { strong: true, highlight: true })}
                      {t.fine_523_B !== "0.00" && line("(+) Fine, CPC art. 523 (B)", t.fine_523_B)}
                      {t.fee_523_C !== "0.00" && line("(+) Fees, CPC art. 523 (C)", t.fee_523_C)}
                      {line("Creditor's amount", t.creditor_amount)}
                      {note && <p className="pb-1 pt-0.5 text-[11px] leading-snug text-muted">{note}</p>}
                      {t.contract_fees !== null && (
                        <div className="rounded-md border border-dashed border-line bg-surface/60 px-2 py-1.5 text-xs text-muted">
                          <div className="flex justify-between py-0.5">
                            <span>Contract fees ({p.contract_fee_pct}%): informative, not part of the debt</span>
                            <span className="tabular-nums">− {brl(t.contract_fees)}</span>
                          </div>
                          <div className="flex justify-between py-0.5 font-semibold text-ink">
                            <span>Net to the creditor after contract fees</span>
                            <span className="tabular-nums">{brl(t.creditor_after_contract_fees as string)}</span>
                          </div>
                        </div>
                      )}
                      <div className="mt-2 flex items-center justify-between rounded-md border-2 border-accent bg-accent-soft px-4 py-3">
                        <span className="font-bold text-ink">GRAND TOTAL</span>
                        <span className="text-xl font-bold tabular-nums text-accent">{brl(t.grand_total)}</span>
                      </div>
                      {Number(t.grand_total) < 0 && (
                        <div className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-2.5 text-xs leading-relaxed text-amber-800">
                          <strong>⚠ Negative balance:</strong> the deductions and abatements exceed the updated credit. Check the entered
                          amounts; if the negative balance is right, there is no credit to enforce.
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>

              <p className="mt-6 text-[10px] leading-relaxed text-muted">
                Produced by a deterministic engine over official central-bank indices (SGS API) versioned in git. Interest follows
                conventions validated against the TJDFT public calculator (JuriscalcWeb) and CMN Resolution 5,171/2024. Every total is
                the exact sum of the displayed components (CPC art. 524, I).
              </p>
            </div>
          </div>
        )}
      </main>

      <div className="no-print fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 p-3 backdrop-blur sm:hidden">
        <div className="flex items-center gap-3">
          {installments.length > 0 && (
            <div className="min-w-0 text-[11px] leading-tight text-muted">
              <p className="font-semibold text-ink">
                {installments.length} amount{installments.length > 1 ? "s" : ""}
              </p>
              <p className="truncate tabular-nums">{brl(nominalSum.toFixed(2))} nominal</p>
            </div>
          )}
          {calculateButton("flex-1 px-6 py-3 text-sm")}
        </div>
      </div>

      <footer className="no-print border-t border-line bg-white py-4 text-center text-[11px] text-muted">
        <p>
          Court Debt Calculator · a portfolio project by Fillipe Loose ·{" "}
          <a href={REPO_URL} className="font-semibold text-accent hover:underline">
            source on GitHub
          </a>
        </p>
        <p className="mt-0.5">Amounts in Brazilian reais (R$ 1.234,56); dates as dd/mm/yyyy. Not legal advice.</p>
      </footer>
    </>
  );
}
