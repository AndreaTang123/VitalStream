import { redirect } from "next/navigation";
import { loadUser } from "@/lib/server/loadUser";
import { CurrentUserProvider } from "@/lib/currentUser";
import { AppShell } from "@/components/AppShell";

export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  // middleware.ts already redirects when there's no refresh cookie at all;
  // this is the "real" check — it actually calls FastAPI, so an expired/
  // revoked session still lands back on /login instead of a broken shell.
  const user = await loadUser();
  if (!user) {
    redirect("/login");
  }

  return (
    <CurrentUserProvider user={user}>
      <AppShell>{children}</AppShell>
    </CurrentUserProvider>
  );
}
