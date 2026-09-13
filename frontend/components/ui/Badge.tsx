import { clsx } from "clsx";
import type { Role } from "@/lib/api-types";

const roleLabel: Record<Role, string> = {
  patient: "Patient",
  coach: "Coach",
  admin: "Operator",
};

const roleClasses: Record<Role, string> = {
  patient: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  coach: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  admin: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};

export function RoleBadge({ role }: { role: Role }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        roleClasses[role],
      )}
    >
      {roleLabel[role]}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const isDenied = status === "denied";
  const isError = status === "error";
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        isDenied && "border-danger/40 bg-danger/15 text-red-300",
        isError && "border-warning/40 bg-warning/15 text-amber-300",
        !isDenied && !isError && "border-border bg-slate-800 text-muted",
      )}
    >
      {status}
    </span>
  );
}
