"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/States";
import { InsightCard } from "@/components/InsightCard";
import { FeatureTrendChart } from "@/components/FeatureTrendChart";
import { InsightHistoryList } from "@/components/InsightHistoryList";
import { GenerateInsightButton } from "@/components/GenerateInsightButton";
import { useDevices } from "@/lib/hooks/useDevices";
import { ApiError } from "@/lib/apiFetch";

/**
 * Shared by /dashboard (a patient viewing themself) and /patients/[id] (a
 * coach viewing an authorized patient) — the only thing that differs is
 * which `userId` gets passed in (week7 Step 7's reuse payoff for keeping
 * this component free of "current user" assumptions).
 */
export function PatientDashboard({ userId }: { userId: string }) {
  const { data: devices, isLoading, error, refetch } = useDevices();
  const patientDevices = devices?.filter((d) => d.user_id === userId) ?? [];
  const primaryDevice = patientDevices[0];

  if (isLoading) {
    return (
      <Card>
        <CardSkeleton />
      </Card>
    );
  }

  if (error) {
    return (
      <ErrorState
        message={error instanceof ApiError ? error.detail : "Failed to load devices"}
        onRetry={() => refetch()}
      />
    );
  }

  if (!primaryDevice) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>设备</CardTitle>
        </CardHeader>
        <EmptyState
          title="还没有数据，先绑定设备并启动模拟器"
          description="patient 账号：POST /api/v1/devices 绑定一个设备，然后运行 device_simulator.replay --device-id <id>。"
        />
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted">
          Device <span className="text-foreground">{primaryDevice.device_type}</span> ·{" "}
          {primaryDevice.status}
        </div>
        <GenerateInsightButton userId={userId} deviceId={primaryDevice.id} />
      </div>

      <InsightCard userId={userId} />
      <FeatureTrendChart deviceId={primaryDevice.id} />
      <InsightHistoryList userId={userId} />
    </div>
  );
}
