/** Shared-password session (edge safe: Web Crypto).
 *  With APP_PASSWORD unset, the app is open (development and the public demo). */

// Version of the session signature. Bump it to INVALIDATE every existing session at once
// (e.g. when the cookie policy changes): old cookies stop matching and everyone signs in again.
const LABEL = "court-debt-calculator-session-v1";

export async function sessionSignature(password: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(LABEL));
  return Array.from(new Uint8Array(mac))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export const COOKIE_NAME = "cdc_session";
