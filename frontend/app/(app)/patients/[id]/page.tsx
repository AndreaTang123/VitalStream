"use client";

import { PatientDashboard } from "@/components/PatientDashboard";
import { RoleGate } from "@/components/RoleGate";
import { CardSkeleton, ForbiddenState } from "@/components/ui/States";
import { Card } from "@/components/ui/Card";
import { useInsights } from "@/lib/hooks/useInsights";
import { ApiError } from "@/lib/apiFetch";

function PatientDetail({ patientId }: { patientId: string }) {
  // Same query InsightCard makes (shared cache key, so this doesn't cost an
  // extra request) — used here purely to learn "was this 403'd" before
  // rendering a page full of widgets that would each show their own error.
  // Step 7: the whole page should read as one clean "access denied", not a
  // stack of broken cards.
  const { error, isLoading } = useInsights(patientId, 1);

  if (isLoading) {
    return (
      <Card>
        <CardSkeleton />
      </Card>
    );
  }

  if (error instanceof ApiError && error.status === 403) {
    return (
      <ForbiddenState message="你没有权限访问该患者的数据 — 这次访问已被记录在审计日志中（可在'审计日志'页面查看）。" />
    );
  }

  return <PatientDashboard userId={patientId} />;
}

export default function PatientDetailPage({ params }: { params: { id: string } }) {
  return (
    <RoleGate roles={["coach", "admin"]}>
      <h1 className="mb-6 text-lg font-semibold text-foreground">患者详情</h1>
      <PatientDetail patientId={params.id} />
    </RoleGate>
  );
}
