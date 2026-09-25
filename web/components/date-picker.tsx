"use client";

import { useEffect, useRef, useState } from "react";

const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const isoToBR = (iso: string) =>
  /^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso.slice(8)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "";

function mask(digits: string): string {
  const d = digits.replace(/\D/g, "").slice(0, 8);
  if (d.length <= 2) return d;
  if (d.length <= 4) return `${d.slice(0, 2)}/${d.slice(2)}`;
  return `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}`;
}

function brToISO(br: string): string | null {
  const m = br.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!m) return null;
  const [, dd, mm, yyyy] = m;
  const date = new Date(Number(yyyy), Number(mm) - 1, Number(dd));
  const valid =
    date.getFullYear() === Number(yyyy) && date.getMonth() === Number(mm) - 1 && date.getDate() === Number(dd);
  return valid ? `${yyyy}-${mm}-${dd}` : null;
}

interface Props {
  value: string; // ISO "2026-05-22" or ""
  onChange: (iso: string) => void;
  testid?: string;
  clearable?: boolean;
  placeholder?: string;
}

export default function DatePicker({ value, onChange, testid, clearable = false, placeholder = "dd/mm/yyyy" }: Props) {
  const [text, setText] = useState(isoToBR(value));
  const [open, setOpen] = useState(false);
  const now = new Date();
  const [year, setYear] = useState(value ? Number(value.slice(0, 4)) : now.getFullYear());
  const [month, setMonth] = useState(value ? Number(value.slice(5, 7)) - 1 : now.getMonth());
  const root = useRef<HTMLDivElement>(null);

  // syncs the typed text and the visible month when the parent changes the value (the
  // "adjusting state when a prop changes" pattern: set during render, not in an effect)
  const [syncedValue, setSyncedValue] = useState(value);
  if (value !== syncedValue) {
    setSyncedValue(value);
    setText(isoToBR(value));
    if (value) {
      setYear(Number(value.slice(0, 4)));
      setMonth(Number(value.slice(5, 7)) - 1);
    }
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

  const onType = (raw: string) => {
    const masked = mask(raw);
    setText(masked);
    if (masked.length === 10) {
      const iso = brToISO(masked);
      if (iso) onChange(iso);
    } else if (masked === "") {
      onChange("");
    }
  };

  const incomplete = text.length > 0 && text.length < 10;
  const invalid = text.length === 10 && !brToISO(text);

  const previousMonth = () => {
    if (month === 0) {
      setMonth(11);
      setYear(year - 1);
    } else setMonth(month - 1);
  };
  const nextMonth = () => {
    if (month === 11) {
      setMonth(0);
      setYear(year + 1);
    } else setMonth(month + 1);
  };

  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const todayISO = new Date().toISOString().slice(0, 10);
  const isoOf = (day: number) => `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

  const pick = (iso: string) => {
    onChange(iso);
    setOpen(false);
  };

  const years: number[] = [];
  for (let y = 1990; y <= now.getFullYear() + 2; y++) years.push(y);

  return (
    <div ref={root} className="relative">
      <div className="relative">
        <input
          data-testid={testid}
          className={`field pr-9 ${invalid ? "border-red-400" : incomplete ? "border-amber-300" : ""}`}
          inputMode="numeric"
          placeholder={placeholder}
          value={text}
          onChange={(e) => onType(e.target.value)}
          onFocus={() => setOpen(false)}
        />
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted transition-colors hover:text-accent"
          aria-label="open calendar"
        >
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
            <rect x="3" y="5" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
            <path d="M3 8.5h14M7 3v3M13 3v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {open && (
        <div className="animate-enter absolute z-50 mt-1 w-72 rounded-lg border border-line bg-white p-3 shadow-xl">
          <div className="mb-2 flex items-center gap-1">
            <button type="button" onClick={previousMonth} className="rounded p-1.5 text-ink transition-colors hover:bg-surface" aria-label="previous month">
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
                <path d="M12 4l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="flex-1 rounded-md border border-line px-1.5 py-1 text-xs font-semibold text-ink outline-none focus:border-accent"
            >
              {MONTHS.map((name, i) => (
                <option key={name} value={i}>
                  {name}
                </option>
              ))}
            </select>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="rounded-md border border-line px-1.5 py-1 text-xs font-semibold text-ink outline-none focus:border-accent"
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            <button type="button" onClick={nextMonth} className="rounded p-1.5 text-ink transition-colors hover:bg-surface" aria-label="next month">
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
                <path d="M8 4l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>

          <div className="grid grid-cols-7 gap-0.5 text-center">
            {WEEKDAYS.map((d, i) => (
              <span key={i} className="py-1 text-[10px] font-bold text-muted">
                {d}
              </span>
            ))}
            {Array.from({ length: firstWeekday }).map((_, i) => (
              <span key={`e${i}`} />
            ))}
            {Array.from({ length: daysInMonth }).map((_, i) => {
              const day = i + 1;
              const iso = isoOf(day);
              const selected = iso === value;
              const isToday = iso === todayISO;
              return (
                <button
                  key={iso}
                  type="button"
                  onClick={() => pick(iso)}
                  className={`rounded-md py-1.5 text-xs font-medium transition-colors ${
                    selected
                      ? "bg-accent font-bold text-white"
                      : isToday
                        ? "border border-accent text-ink hover:bg-accent-soft"
                        : "text-ink hover:bg-accent-soft"
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>

          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => pick(todayISO)}
              className="flex-1 rounded-md border border-dashed border-line py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted transition-colors hover:border-accent hover:text-accent"
            >
              today
            </button>
            {clearable && value && (
              <button
                type="button"
                onClick={() => {
                  onChange("");
                  setText("");
                  setOpen(false);
                }}
                className="flex-1 rounded-md border border-dashed border-line py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted transition-colors hover:border-red-400 hover:text-red-500"
              >
                clear
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
