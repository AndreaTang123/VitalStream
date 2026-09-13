import { NextResponse } from "next/server";
import { BackendError, backendMe } from "@/lib/server/backend";
import { readAccessToken } from "@/lib/server/cookies";
import { refreshAccessToken } from "@/lib/server/refresh";

export async function GET() {
  const accessToken = readAccessToken();
  if (!accessToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  try {
    const user = await backendMe(accessToken);
    return NextResponse.json(user);
  } catch (err) {
    if (err instanceof BackendError && err.status === 401) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        try {
          const user = await backendMe(refreshed);
          return NextResponse.json(user);
        } catch {
          // fall through to 401 below
        }
      }
    }
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
}
