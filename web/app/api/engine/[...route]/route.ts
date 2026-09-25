import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** Server-side proxy to the engine API: the token stays on the server (never in the browser
 *  bundle) and CORS is no longer needed. */

export const maxDuration = 60; // the extraction can take tens of seconds

const ALLOWED_ROUTES = new Set(["health", "series", "calculate", "extract", "statement"]);

const base = () => process.env.API_URL ?? "http://localhost:8000";

const authorization = (): Record<string, string> => {
  const token = process.env.CALC_API_TOKEN;
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// arrayBuffer preserves binary responses (the statement PDF) as well as JSON
const passThrough = async (response: Response) => {
  const headers: Record<string, string> = {
    "content-type": response.headers.get("content-type") ?? "application/json",
  };
  const disposition = response.headers.get("content-disposition");
  if (disposition) headers["content-disposition"] = disposition;
  return new NextResponse(await response.arrayBuffer(), { status: response.status, headers });
};

type Context = { params: Promise<{ route: string[] }> };

export async function GET(_request: NextRequest, context: Context) {
  const { route } = await context.params;
  if (!ALLOWED_ROUTES.has(route[0])) {
    return NextResponse.json({ detail: "Route not allowed." }, { status: 404 });
  }
  const response = await fetch(`${base()}/${route.join("/")}`, {
    headers: authorization(),
    cache: "no-store",
  });
  return passThrough(response);
}

export async function POST(request: NextRequest, context: Context) {
  const { route } = await context.params;
  if (!ALLOWED_ROUTES.has(route[0])) {
    return NextResponse.json({ detail: "Route not allowed." }, { status: 404 });
  }
  const url = `${base()}/${route.join("/")}`;
  const type = request.headers.get("content-type") ?? "";

  const response = type.includes("multipart/form-data")
    ? await fetch(url, { method: "POST", headers: authorization(), body: await request.formData() })
    : await fetch(url, {
        method: "POST",
        headers: { ...authorization(), "content-type": "application/json" },
        body: await request.text(),
      });
  return passThrough(response);
}
