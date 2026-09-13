"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/States";
import { useInsightHistory } from "@/lib/hooks/useInsightHistory";
import { ApiError } from "@/lib/apiFetch";
import { relativeTime, absoluteTime, formatCost } from "@/lib/format";

export function InsightHistoryList({ userId }: { userId: string }) {
  const { data, isLoading, error, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInsightHistory(userId);

  const rows = data?.pages.flat() ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>历史洞察</CardTitle>
      </CardHeader>

      {isLoading && <CardSkeleton />}

      {error && (
        <ErrorState
          message={error instanceof ApiError ? error.detail : "Failed to load history"}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !error && rows.length === 0 && (
        <EmptyState title="还没有历史记录" description="生成一条洞察，或者等模拟器跑出下一条。" />
      )}

      {!isLoading && !error && rows.length > 0 && (
        <ul className="divide-y divide-border">
          {rows.map((insight) => (
            <li key={insight.id} className="py-3 first:pt-0 last:pb-0">
              <div className="flex items-center justify-between text-xs text-muted">
                <span title={absoluteTime(insight.created_at)}>{relativeTime(insight.created_at)}</span>
                <span className="flex items-center gap-2">
                  {insight.source === "device" && (
                    <span className="rounded-full border border-border px-1.5 py-0.5">auto</span>
                  )}
                  {insight.cache_hit && (
                    <span className="rounded-full border border-success/40 bg-success/10 px-1.5 py-0.5 text-success">
                      cache hit
                    </span>
                  )}
                  {insight.cost_usd !== null && <span>{formatCost(insight.cost_usd)}</span>}
                </span>
              </div>
              <p className="mt-1 text-sm text-foreground">{insight.content}</p>
            </li>
          ))}
        </ul>
      )}

      {hasNextPage && (
        <Button
          variant="secondary"
          className="mt-4 w-full"
          disabled={isFetchingNextPage}
          onClick={() => fetchNextPage()}
        >
          {isFetchingNextPage ? "Loading…" : "加载更多"}
        </Button>
      )}
    </Card>
  );
}
