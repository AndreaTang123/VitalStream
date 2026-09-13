"use client";

import { FormEvent, useState } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/Badge";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/States";
import { RoleGate } from "@/components/RoleGate";
import { useConfirm } from "@/components/ConfirmDialog";
import {
  ALGO_NAME,
  useConfigVersions,
  usePromote,
  usePublishCanary,
  useRegisterStable,
  useRollback,
} from "@/lib/hooks/useConfig";
import { ApiError } from "@/lib/apiFetch";
import { absoluteTime } from "@/lib/format";

function ConfigTable() {
  const { data, isLoading, error, refetch } = useConfigVersions();
  const registerStable = useRegisterStable();
  const publishCanary = usePublishCanary();
  const promote = usePromote();
  const rollback = useRollback();
  const { confirm, dialog } = useConfirm();

  const [newVersion, setNewVersion] = useState("");
  const [rolloutPct, setRolloutPct] = useState(20);

  function handleRegister(e: FormEvent) {
    e.preventDefault();
    if (!newVersion) return;
    registerStable.mutate(newVersion, { onSuccess: () => setNewVersion("") });
  }

  function handleCanary(e: FormEvent) {
    e.preventDefault();
    if (!newVersion) return;
    publishCanary.mutate({ version: newVersion, rolloutPct }, { onSuccess: () => setNewVersion("") });
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>{ALGO_NAME} — 版本</CardTitle>
        </CardHeader>

        {isLoading && <CardSkeleton />}
        {error && (
          <ErrorState
            message={error instanceof ApiError ? error.detail : "Failed to load versions"}
            onRetry={() => refetch()}
          />
        )}
        {!isLoading && !error && data && data.length === 0 && (
          <EmptyState title="还没有注册任何版本" description="用下面的表单注册第一个 stable 版本。" />
        )}
        {!isLoading && !error && data && data.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                <th className="pb-2">Version</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Rollout</th>
                <th className="pb-2">Created</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.map((v) => (
                <tr key={v.version}>
                  <td className="py-2 text-foreground">{v.version}</td>
                  <td className="py-2">
                    <StatusBadge status={v.status} />
                  </td>
                  <td className="py-2 text-muted">{v.rollout_pct}%</td>
                  <td className="py-2 text-muted">{absoluteTime(v.created_at)}</td>
                  <td className="py-2 text-right">
                    {v.status !== "retired" && (
                      <Button
                        variant="danger"
                        className="px-2 py-1 text-xs"
                        onClick={() =>
                          confirm(
                            `确定要回滚版本 ${v.version} 吗？这会立刻影响正在使用该算法的设备。`,
                            () => rollback.mutate(v.version),
                          )
                        }
                      >
                        Rollback
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>注册 / 灰度发布</CardTitle>
          </CardHeader>
          <form onSubmit={handleCanary} className="space-y-3">
            <input
              value={newVersion}
              onChange={(e) => setNewVersion(e.target.value)}
              placeholder="version, e.g. v2-naive-wideband"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                max={100}
                value={rolloutPct}
                onChange={(e) => setRolloutPct(Number(e.target.value))}
                className="w-24 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
              />
              <span className="text-sm text-muted">% rollout</span>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={!newVersion || publishCanary.isPending}>
                {publishCanary.isPending ? "Publishing…" : "Publish canary"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={!newVersion || registerStable.isPending}
                onClick={handleRegister}
              >
                Register as stable
              </Button>
            </div>
          </form>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Promote canary → stable</CardTitle>
          </CardHeader>
          <p className="mb-3 text-sm text-muted">
            把当前 canary 提升为 100% rollout 的 stable 版本，旧版本自动退役。
          </p>
          <Button variant="secondary" disabled={promote.isPending} onClick={() => promote.mutate()}>
            {promote.isPending ? "Promoting…" : "Promote"}
          </Button>
        </Card>
      </div>

      {dialog}
    </div>
  );
}

export default function ConfigPage() {
  return (
    <RoleGate roles={["admin"]}>
      <h1 className="mb-6 text-lg font-semibold text-foreground">系统管理 — 算法版本</h1>
      <ConfigTable />
    </RoleGate>
  );
}
