"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { RoleBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useCurrentUser } from "@/lib/currentUser";

interface NavItem {
  href: string;
  label: string;
  roles: Array<"patient" | "coach" | "admin">;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "我的健康", roles: ["patient"] },
  { href: "/patients", label: "我的患者", roles: ["coach", "admin"] },
  { href: "/admin/config", label: "系统管理", roles: ["admin"] },
  { href: "/admin/audit", label: "审计日志", roles: ["coach", "admin"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useCurrentUser();
  const pathname = usePathname();
  const items = NAV_ITEMS.filter((item) => item.roles.includes(user.role));

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-border bg-surface px-4 py-6">
        <div className="mb-8 px-2 text-lg font-semibold text-foreground">VitalStream</div>
        <nav className="space-y-1">
          {items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active ? "bg-accent/15 text-accent" : "text-muted hover:bg-slate-800 hover:text-foreground",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
          <div />
          <div className="flex items-center gap-3">
            <RoleBadge role={user.role} />
            <span className="text-sm text-foreground">{user.display_name ?? user.email}</span>
            <Button variant="ghost" onClick={logout}>
              Log out
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
