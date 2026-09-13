"use client";

import Link from "next/link";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/States";
import { RoleGate } from "@/components/RoleGate";
import { usePatients } from "@/lib/hooks/usePatients";
import { ApiError } from "@/lib/apiFetch";
import { relativeTime } from "@/lib/format";

function PatientsList() {
  const { data, isLoading, error, refetch } = usePatients();

  return (
    <Card>
      <CardHeader>
        <CardTitle>授权患者</CardTitle>
      </CardHeader>

      {isLoading && <CardSkeleton />}

      {error && (
        <ErrorState
          message={error instanceof ApiError ? error.detail : "Failed to load patients"}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !error && data && data.length === 0 && (
        <EmptyState
          title="还没有被授权的患者"
          description="让 operator 通过 POST /api/v1/coach/patients 建立授权关系。"
        />
      )}

      {!isLoading && !error && data && data.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
              <th className="pb-2">Patient</th>
              <th className="pb-2">Devices</th>
              <th className="pb-2">Latest insight</th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.map((patient) => (
              <tr key={patient.id}>
                <td className="py-3 text-foreground">{patient.display_name ?? patient.email}</td>
                <td className="py-3 text-muted">{patient.device_count}</td>
                <td className="py-3 text-muted">
                  {patient.latest_insight ? (
                    <span title={patient.latest_insight.content}>
                      {relativeTime(patient.latest_insight.created_at)} —{" "}
                      {patient.latest_insight.content.slice(0, 40)}
                      {patient.latest_insight.content.length > 40 ? "…" : ""}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="py-3 text-right">
                  <Link href={`/patients/${patient.id}`} className="text-accent hover:underline">
                    View →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export default function PatientsPage() {
  return (
    <RoleGate roles={["coach", "admin"]}>
      <h1 className="mb-6 text-lg font-semibold text-foreground">我的患者</h1>
      <PatientsList />
    </RoleGate>
  );
}
