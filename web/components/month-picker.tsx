"use client";

import { useEffect, useRef, useState } from "react";
import { monthLabel } from "@/lib/format";

const SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

interface Props {
  value: string; // "2026-05"
  onChange: (month: string) => void;
  /** Last selectable month (e.g. the latest published). */
  maximum?: string;
  minimum?: string;
  maximumLabel?: string;
}

export default function MonthPicker({ value, onChange, maximum, minimum = "1994-07", maximumLabel = "latest published" }: Props) {
  const [open, setOpen] = useState(false);
  const [year, setYear] = useState(() => Number(value?.slice(0, 4)) || new Date().getFullYear());
  const root = useRef<HTMLDivElement>(null);

  // follows the parent's value into the visible year (set during render, not in an effect)
  const [syncedValue, setSyncedValue] = useState(value);
  if (value !== syncedValue) {
    setSyncedValue(value);
    if (value) setYear(Number(value.slice(0, 4)));
  }

  useEffect(() => {
    if (!open) return;
    const outside = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", outside);
      document.removeEventListener("keydown", key);
    };
  }, [open]);

  const minYear = Number(minimum.slice(0, 4));
  const maxYear = maximum ? Number(maximum.slice(0, 4)) : new Date().getFullYear() + 1;

  const monthOf = (y: number, index: number) => `${y}-${String(index + 1).padStart(2, "0")}`;
  const disabled = (m: string) => m < minimum || (!!maximum && m > maximum);

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="field flex items-center justify-between text-left"
      >
        <span className={value ? "" : "text-muted"}>{value ? monthLabel(value) : "select a month"}</span>
        <svg className="h-4 w-4 text-muted" viewBox="0 0 20 20" fill="none" aria-hidden>
          <rect x="3" y="5" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
          <path d="M3 8.5h14M7 3v3M13 3v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <div className="animate-enter absolute z-50 mt-1 w-64 rounded-lg border border-line bg-white p-3 shadow-xl">
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setYear(year - 1)}
              disabled={year <= minYear}
              className="rounded p-1.5 text-ink transition-colors hover:bg-surface disabled:opacity-25"
              aria-label="previous year"
            >
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
                <path d="M12 4l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <span className="text-sm font-bold text-ink">{year}</span>
            <button
              type="button"
              onClick={() => setYear(year + 1)}
              disabled={year >= maxYear}
              className="rounded p-1.5 text-ink transition-colors hover:bg-surface disabled:opacity-25"
              aria-label="next year"
            >
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
                <path d="M8 4l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>

          <div className="grid grid-cols-4 gap-1">
            {SHORT_MONTHS.map((name, i) => {
              const m = monthOf(year, i);
              const selected = m === value;
              const blocked = disabled(m);
              return (
                <button
                  key={m}
                  type="button"
                  disabled={blocked}
                  onClick={() => {
                    onChange(m);
                    setOpen(false);
                  }}
                  className={`rounded-md py-2 text-xs font-semibold uppercase transition-colors ${
                    selected ? "bg-accent text-white" : blocked ? "cursor-not-allowed text-line" : "text-ink hover:bg-accent-soft"
                  }`}
                >
                  {name}
                </button>
              );
            })}
          </div>

          {maximum && (
            <button
              type="button"
              onClick={() => {
                onChange(maximum);
                setYear(Number(maximum.slice(0, 4)));
                setOpen(false);
              }}
              className="mt-2 w-full rounded-md border border-dashed border-line py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
            >
              {maximumLabel}: {monthLabel(maximum)}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
