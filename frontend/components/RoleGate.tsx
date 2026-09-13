"use client";

import { ForbiddenState } from "@/components/ui/States";
import { useCurrentUser } from "@/lib/currentUser";
import type { Role } from "@/lib/api-types";

/**
 * Step 4's "手动在地址栏敲 /admin/config 用 patient 账号访问，页面显示'无权
 * 访问'而不是崩溃或白屏". Purely cosmetic, same as middleware.ts — the real
 * gate is FastAPI's `require_role`/`authorize_*` dependencies (Week 6); this
 * only avoids rendering a page full of components that would each 403.
 */
export function RoleGate({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { user } = useCurrentUser();
  if (!roles.includes(user.role)) {
    return <ForbiddenState message="你的账号角色没有权限查看这个页面。" />;
  }
  return <>{children}</>;
}
