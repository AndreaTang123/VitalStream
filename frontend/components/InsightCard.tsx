"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/States";
import { useInsights } from "@/lib/hooks/useInsights";
import { ApiError } from "@/lib/apiFetch";
import { relativeTime, absoluteTime, formatCost } from "@/lib/format";

export function InsightCard({ userId }: { userId: string }) {
  const { data, isLoading, error, refetch } = useInsights(userId, 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle>最新健康洞察</CardTitle>
      </CardHeader>

      {isLoading && <CardSkeleton />}

      {error && (
        <ErrorState
          message={error instanceof ApiError ? error.detail : "Failed to load insight"}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !error && (!data || data.length === 0) && (
        <EmptyState
          title="还没有数据"
          description="先绑定设备并启动模拟器 (device_simulator.replay)，几秒后回来看看。"
        />
      )}

      {!isLoading && !error && data && data.length > 0 && (
        <div>
          <p className="text-sm leading-relaxed text-foreground">{data[0].content}</p>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted sm:grid-cols-4">
            <div>
              <dt className="uppercase tracking-wide">Generated</dt>
              <dd title={absoluteTime(data[0].created_at)} className="text-foreground">
                {relativeTime(data[0].created_at)}
              </dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide">Prompt</dt>
              <dd className="text-foreground">{data[0].prompt_version ?? "—"}</dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide">Cache</dt>
              <dd className="text-foreground">
                {data[0].cache_hit === null ? "—" : data[0].cache_hit ? "hit" : "miss"}
              </dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide">Cost</dt>
              <dd className="text-foreground">
                {data[0].cost_usd === null ? "—" : formatCost(data[0].cost_usd)}
              </dd>
            </div>
          </dl>
        </div>
      )}
    </Card>
  );
}
