"use client";

import type { ExtractedField } from "@/lib/api";

export const labelClass = "mb-1 block text-[11px] font-bold uppercase tracking-wide text-ink";

export function Card({ title, extra, children }: { title: string; extra?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="mb-4 rounded-lg border border-line bg-white p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="border-l-4 border-accent pl-2 text-[13px] font-bold uppercase tracking-wider text-ink">{title}</h2>
        {extra}
      </div>
      {children}
    </section>
  );
}

/** Badge next to the label of a field pre-filled by the extraction: colour by confidence,
 *  the source excerpt in the title (native tooltip). */
export function AiBadge({ field }: { field?: ExtractedField | null }) {
  if (!field) return null;
  if (field.value === null) {
    return (
      <span className="ml-2 rounded-full border border-amber-300 bg-amber-50 px-2 py-px text-[9px] font-bold normal-case tracking-normal text-amber-700">
        not identified
      </span>
    );
  }
  const high = field.confidence >= 0.85;
  return (
    <span
      title={field.quote ? `Excerpt ${field.document ? `from ${field.document}` : "of the document"}: “${field.quote}”` : undefined}
      className={`ml-2 cursor-help rounded-full border px-2 py-px text-[9px] font-bold normal-case tracking-normal ${
        high ? "border-emerald-300 bg-emerald-50 text-emerald-700" : "border-amber-300 bg-amber-50 text-amber-700"
      }`}
    >
      ⚡ AI {Math.round(field.confidence * 100)}%
    </span>
  );
}

export function Pills<T extends string>({
  options,
  value,
  onChange,
  columns = "grid-cols-2 lg:grid-cols-4",
}: {
  options: { v: T; title: string; detail?: string }[];
  value: T;
  onChange: (v: T) => void;
  columns?: string;
}) {
  return (
    <div className={`grid gap-2 ${columns}`}>
      {options.map((o) => (
        <button
          key={o.v}
          type="button"
          onClick={() => onChange(o.v)}
          className={`rounded-md border px-3 py-2 text-left transition-all active:scale-[0.98] ${
            value === o.v ? "border-accent bg-accent-soft shadow-sm" : "border-line bg-white hover:border-muted"
          }`}
        >
          <span className={`block text-xs font-bold ${value === o.v ? "text-ink" : "text-muted"}`}>{o.title}</span>
          {o.detail && <span className="mt-0.5 block text-[10px] leading-tight text-muted">{o.detail}</span>}
        </button>
      ))}
    </div>
  );
}

/** A toggle chip: "✓ Fine of" style switch used by the optional sections. */
export function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-4 py-1.5 text-sm font-semibold transition-all active:scale-[0.97] ${
        on ? "border-accent bg-accent-soft text-ink" : "border-line bg-white text-muted hover:border-muted"
      }`}
    >
      {on ? "✓ " : ""}
      {children}
    </button>
  );
}

export function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
