import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { COOKIE_NAME, sessionSignature } from "@/lib/session";

export async function POST(request: NextRequest) {
  const password = process.env.APP_PASSWORD;
  if (!password) return NextResponse.json({ ok: true }); // open app

  const body = await request.json().catch(() => null);
  if (!body?.password || body.password !== password) {
    return NextResponse.json({ detail: "Wrong password." }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  // a SESSION cookie (no maxAge/expires): it expires when the browser closes
  response.cookies.set(COOKIE_NAME, await sessionSignature(password), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  });
  return response;
}
