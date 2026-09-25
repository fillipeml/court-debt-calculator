"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SignIn() {
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const signIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const response = await fetch("/api/sign-in", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    setLoading(false);
    if (response.ok) router.push("/");
    else setError("Wrong password.");
  };

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.15fr_1fr]">
      <section className="relative hidden overflow-hidden bg-ink lg:block">
        <div className="absolute inset-0 opacity-20" style={{ background: "radial-gradient(circle at 30% 30%, #047857 0, transparent 55%)" }} />
        <div className="absolute bottom-0 left-0 p-12">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/mark.svg" alt="" className="mb-6 h-12 w-12" />
          <p className="text-5xl font-semibold leading-tight text-white">
            The model interprets.
            <br />
            The engine computes.
          </p>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-line">
            Court debt updates with parity to the cent against public court calculators and a neutral
            statement ready for the case file.
          </p>
        </div>
      </section>

      <section className="flex items-center justify-center bg-white px-6 py-16">
        <form onSubmit={signIn} className="w-full max-w-sm">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/mark.svg" alt="" className="mb-8 h-10 w-10 lg:hidden" />
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-accent">Court Debt Calculator</p>
          <h1 className="mt-1 text-3xl font-semibold text-ink">Sign in</h1>
          <p className="mb-8 mt-1 text-sm text-muted">This instance is protected by a shared password.</p>

          <label className="mb-1 block text-xs font-semibold text-muted">Password</label>
          <div className="relative mb-5">
            <input
              type={show ? "text" : "password"}
              autoFocus
              autoComplete="current-password"
              className="field py-2.5 pr-10"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              onClick={() => setShow(!show)}
              aria-label={show ? "Hide password" : "Show password"}
              className="absolute inset-y-0 right-0 flex items-center px-3 text-muted transition-colors hover:text-ink"
            >
              {show ? (
                <svg className="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg className="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>

          {error && (
            <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-800">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !password}
            className="w-full rounded-md bg-accent py-2.5 text-sm font-bold uppercase tracking-wide text-white transition-all hover:opacity-90 disabled:opacity-40"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
