import { NextRequest, NextResponse } from "next/server";
import { BackendError, backendLogin, backendMe } from "@/lib/server/backend";
import { setAuthCookies } from "@/lib/server/cookies";

export async function POST(request: NextRequest) {
  const { email, password } = await request.json();
  if (typeof email !== "string" || typeof password !== "string") {
    return NextResponse.json({ detail: "email and password are required" }, { status: 400 });
  }

  try {
    const tokens = await backendLogin(email, password);
    // Tokens never reach the response body — only the httpOnly cookies get
    // them (week7 Step 2: BFF mode). The browser only ever sees the user.
    setAuthCookies(tokens.access_token, tokens.refresh_token);
    const user = await backendMe(tokens.access_token);
    return NextResponse.json(user);
  } catch (err) {
    if (err instanceof BackendError) {
      return NextResponse.json(err.body ?? { detail: "login failed" }, { status: err.status });
    }
    return NextResponse.json({ detail: "api service unreachable" }, { status: 502 });
  }
}
