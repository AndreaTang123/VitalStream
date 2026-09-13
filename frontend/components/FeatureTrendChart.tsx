"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/States";
import { useFeatures, type RangeHours } from "@/lib/hooks/useFeatures";
import { ApiError } from "@/lib/apiFetch";

const RANGES: RangeHours[] = [1, 6, 24];
const SERIES_COLORS: Record<string, string> = {
  heart_rate: "#38bdf8",
  hrv: "#34d399",
  activity: "#fbbf24",
};

export function FeatureTrendChart({ deviceId }: { deviceId: string | undefined }) {
  const [range, setRange] = useState<RangeHours>(6);
  const { data, isLoading, error, refetch } = useFeatures(deviceId, range);

  const { points, featureTypes, algoChanges } = useMemo(() => {
    if (!data) return { points: [], featureTypes: [], algoChanges: [] };

    // API returns newest-first; chart wants oldest-first on the x-axis.
    const ascending = [...data].reverse();
    const byTimestamp = new Map<string, Record<string, unknown>>();
    const types = new Set<string>();
    let lastAlgoVersion: string | null = null;
    const changes: { ts: string; version: string }[] = [];

    for (const row of ascending) {
      types.add(row.feature_type);
      const existing = byTimestamp.get(row.window_end) ?? { window_end: row.window_end };
      existing[row.feature_type] = row.value;
      byTimestamp.set(row.window_end, existing);

      if (row.feature_type === "heart_rate" && row.algo_version !== lastAlgoVersion) {
        if (lastAlgoVersion !== null) {
          changes.push({ ts: row.window_end, version: row.algo_version });
        }
        lastAlgoVersion = row.algo_version;
      }
    }

    return {
      points: Array.from(byTimestamp.values()),
      featureTypes: Array.from(types),
      algoChanges: changes,
    };
  }, [data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>特征趋势</CardTitle>
        <div className="flex gap-1">
          {RANGES.map((hours) => (
            <Button
              key={hours}
              variant={range === hours ? "primary" : "secondary"}
              className="px-2 py-1 text-xs"
              onClick={() => setRange(hours)}
            >
              {hours}h
            </Button>
          ))}
        </div>
      </CardHeader>

      {!deviceId && (
        <EmptyState title="还没有设备" description="先绑定一个模拟设备才能看到趋势图。" />
      )}

      {deviceId && isLoading && <CardSkeleton />}

      {deviceId && error && (
        <ErrorState
          message={error instanceof ApiError ? error.detail : "Failed to load features"}
          onRetry={() => refetch()}
        />
      )}

      {deviceId && !isLoading && !error && points.length === 0 && (
        <EmptyState
          title="这个时间范围内还没有数据"
          description="数据截止到模拟器最后一次运行的时间 — 试试更大的时间范围，或重新启动 device_simulator。"
        />
      )}

      {deviceId && !isLoading && !error && points.length > 0 && (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="window_end"
                tickFormatter={(v: string) => format(new Date(v), "HH:mm")}
                stroke="#94a3b8"
                fontSize={11}
              />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip
                labelFormatter={(v: string) => format(new Date(v), "yyyy-MM-dd HH:mm:ss")}
                contentStyle={{ background: "#111827", border: "1px solid #1f2937", fontSize: 12 }}
              />
              {featureTypes.map((type) => (
                <Line
                  key={type}
                  type="monotone"
                  dataKey={type}
                  stroke={SERIES_COLORS[type] ?? "#a78bfa"}
                  dot={false}
                  strokeWidth={2}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
              {/* Week 3's gray-release made visible: each algo_version
                  change (heart_rate only) gets a vertical marker. */}
              {algoChanges.map((change) => (
                <ReferenceLine
                  key={change.ts}
                  x={change.ts}
                  stroke="#f87171"
                  strokeDasharray="4 4"
                  label={{ value: change.version, fill: "#f87171", fontSize: 10, position: "top" }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
