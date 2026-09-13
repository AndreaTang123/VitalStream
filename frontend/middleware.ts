import { NextRequest, NextResponse } from "next/server";
import { REFRESH_COOKIE } from "@/lib/server/cookies";

/**
 * week7 Step 2: redirects logged-out visitors away from protected routes so
 * they don't land on a page that's just going to 401 every request.
 *
 * This is NOT a security boundary — it only checks whether a refresh cookie
 * exists, never validates it, and every real permission decision (role,
 * resource ownership) happens in FastAPI via Week 6's RBAC. A user who
 * forges past this middleware gets nothing they couldn't already get by
 * calling the api service directly; this only exists so the UI doesn't show
 * a blank/broken page while that 401 is in flight.
 */
export function middleware(request: NextRequest) {
  const hasSession = request.cookies.has(REFRESH_COOKIE);
  if (!hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/patients/:path*", "/admin/:path*"],
};
