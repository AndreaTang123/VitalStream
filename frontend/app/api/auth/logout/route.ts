import { NextResponse } from "next/server";
import { backendLogout } from "@/lib/server/backend";
import { clearAuthCookies, readRefreshToken } from "@/lib/server/cookies";

export async function POST() {
  const refreshToken = readRefreshToken();
  if (refreshToken) {
    await backendLogout(refreshToken);
  }
  // Cookies are cleared unconditionally — the user should always end up
  // looking logged-out client-side even if the backend revoke call failed
  // (network blip, token already expired, etc).
  clearAuthCookies();
  return NextResponse.json({ ok: true });
}
