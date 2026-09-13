"use client";

import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { defaultRouteForRole } from "@/lib/roles";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("patient-a@vitalstream.dev");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? "Login failed");
      }
      const user = await response.json();
      // Default landing route depends on role — a coach/admin has no
      // /dashboard (that's patient-only), so falling back to it
      // unconditionally would land them straight on a "forbidden" page.
      const defaultRoute = user.role === "patient" ? "/dashboard" : "/patients";
      const next = searchParams.get("next") ?? defaultRoute;
      router.push(next);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface p-8 shadow-lg">
        <h1 className="text-xl font-semibold text-foreground">VitalStream</h1>
        <p className="mt-1 text-sm text-muted">Sign in to your dashboard</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
          </div>

          {error && <p className="text-sm text-red-300">{error}</p>}

          <Button type="submit" disabled={pending} className="w-full">
            {pending ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-6 text-xs text-muted">
          Seed accounts (run <code>scripts/seed.py</code>): patient-a@vitalstream.dev,
          patient-b@vitalstream.dev, coach-c@vitalstream.dev, admin-o@vitalstream.dev — password{" "}
          <code>password123</code> for all.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
