"use client";

import { useState } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/Badge";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/States";
import { RoleGate } from "@/components/RoleGate";
import { useAuditLogs } from "@/lib/hooks/useAuditLogs";
import { ApiError } from "@/lib/apiFetch";
import { absoluteTime, relativeTime } from "@/lib/format";

const ACTIONS = [
  "insights.read",
  "features.read",
  "insights.generate",
  "config.publish_canary",
  "config.rollback",
  "config.register_stable",
  "config.promote",
  "auth.login_success",
  "auth.login_failed",
  "access.denied",
];

function AuditTable() {
  const [action, setAction] = useState("");
  const [targetUserId, setTargetUserId] = useState("");
  const [deniedOnly, setDeniedOnly] = useState(false);

  const { data, isLoading, error, refetch } = useAuditLogs({
    action: action || undefined,
    targetUserId: targetUserId || undefined,
    status: deniedOnly ? "denied" : undefined,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>审计日志</CardTitle>
      </CardHeader>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={action}
          onChange={(e) => setAction(e.target.value)}
          className="rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"
        >
          <option value="">All actions</option>
          {ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <input
          value={targetUserId}
          onChange={(e) => setTargetUserId(e.target.value)}
          placeholder="target_user_id (UUID)"
          className="w-64 rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"
        />
        <Button
          variant={deniedOnly ? "danger" : "secondary"}
          className="px-2 py-1.5 text-xs"
          onClick={() => setDeniedOnly((v) => !v)}
        >
          {deniedOnly ? "✓ 仅看被拒绝" : "仅看被拒绝"}
        </Button>
      </div>

      {isLoading && <CardSkeleton />}
      {error && (
        <ErrorState
          message={error instanceof ApiError ? error.detail : "Failed to load audit logs"}
          onRetry={() => refetch()}
        />
      )}
      {!isLoading && !error && data && data.length === 0 && (
        <EmptyState title="没有匹配的记录" description="调整上面的筛选条件，或清空后重试。" />
      )}
      {!isLoading && !error && data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                <th className="pb-2 pr-3">Time</th>
                <th className="pb-2 pr-3">Actor</th>
                <th className="pb-2 pr-3">Action</th>
                <th className="pb-2 pr-3">Target</th>
                <th className="pb-2 pr-3">Status</th>
                <th className="pb-2">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.map((log) => (
                <tr key={log.id} className={log.status === "denied" ? "bg-danger/5" : undefined}>
                  <td className="py-2 pr-3 text-muted" title={absoluteTime(log.created_at)}>
                    {relativeTime(log.created_at)}
                  </td>
                  <td className="py-2 pr-3 text-foreground">{log.actor_email ?? "—"}</td>
                  <td className="py-2 pr-3 font-mono text-xs text-foreground">{log.action}</td>
                  <td className="py-2 pr-3 text-muted">{log.target_user_id ?? log.resource_id ?? "—"}</td>
                  <td className="py-2 pr-3">
                    <StatusBadge status={log.status} />
                  </td>
                  <td className="py-2 text-muted">{log.ip_address ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export default function AuditPage() {
  return (
    <RoleGate roles={["coach", "admin"]}>
      <h1 className="mb-6 text-lg font-semibold text-foreground">审计日志</h1>
      <AuditTable />
    </RoleGate>
  );
}
