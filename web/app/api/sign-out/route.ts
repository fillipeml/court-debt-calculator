import { NextResponse } from "next/server";
import { COOKIE_NAME } from "@/lib/session";

/** Ends the session: deletes the cookie and the app asks for the sign-in screen again. */
export async function POST() {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete(COOKIE_NAME);
  return response;
}
