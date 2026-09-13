"use client";

import { PatientDashboard } from "@/components/PatientDashboard";
import { RoleGate } from "@/components/RoleGate";
import { useCurrentUser } from "@/lib/currentUser";

export default function DashboardPage() {
  const { user } = useCurrentUser();
  return (
    <RoleGate roles={["patient"]}>
      <div>
        <h1 className="mb-6 text-lg font-semibold text-foreground">我的健康</h1>
        <PatientDashboard userId={user.id} />
      </div>
    </RoleGate>
  );
}
