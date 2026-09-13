/**
 * week7 Step 3: the one door the browser ever knocks on for api data.
 * Forwards `/api/proxy/<rest>` to `${API_BASE_URL}/api/v1/<rest>` with the
 * access-token cookie turned into an Authorization header, transparently
 * refreshing once on a 401 and retrying, and passing 403 straight through
 * (never treated as "needs a refresh" — see lib/server/refresh.ts).
 */
import { NextRequest, NextResponse } from "next/server";
import { API_BASE_URL, parseBody } from "@/lib/server/backend";
import { readAccessToken } from "@/lib/server/cookies";
import { refreshAccessToken } from "@/lib/server/refresh";

async function forward(request: NextRequest, path: string[], accessToken: string): Promise<Response> {
  const target = new URL(`${API_BASE_URL}/api/v1/${path.join("/")}`);
  target.search = request.nextUrl.search;

  const method = request.method;
  const hasBody = method !== "GET" && method !== "HEAD";

  return fetch(target, {
    method,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      ...(hasBody ? { "Content-Type": "application/json" } : {}),
    },
    body: hasBody ? await request.text() : undefined,
    cache: "no-store",
  });
}

async function handle(request: NextRequest, path: string[]): Promise<NextResponse> {
  const accessToken = readAccessToken();
  if (!accessToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  let response = await forward(request, path, accessToken);

  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (!refreshed) {
      return NextResponse.json({ detail: "session expired" }, { status: 401 });
    }
    response = await forward(request, path, refreshed);
  }

  // 403 passes straight through — it means "you don't have access to this",
  // not "your token is stale"; retrying it after a refresh would just loop.
  const body = await parseBody(response);
  return NextResponse.json(body, { status: response.status });
}

export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  return handle(request, params.path);
}

export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  return handle(request, params.path);
}
