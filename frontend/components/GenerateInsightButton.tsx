"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useGenerateInsight } from "@/lib/hooks/useGenerateInsight";
import { ApiError } from "@/lib/apiFetch";

export function GenerateInsightButton({ userId, deviceId }: { userId: string; deviceId?: string }) {
  const mutation = useGenerateInsight(userId);
  const [justGenerated, setJustGenerated] = useState(false);

  if (!deviceId) return null;

  return (
    <div className="flex items-center gap-3">
      <Button
        onClick={() => {
          setJustGenerated(false);
          mutation.mutate(deviceId, { onSuccess: () => setJustGenerated(true) });
        }}
        disabled={mutation.isPending}
      >
        {mutation.isPending ? "生成中…" : "生成洞察"}
      </Button>
      {justGenerated && !mutation.isPending && (
        <span className="text-xs text-success">新洞察已生成 ✓</span>
      )}
      {mutation.error && (
        <span className="text-xs text-danger">
          {mutation.error instanceof ApiError ? mutation.error.detail : mutation.error.message}
        </span>
      )}
    </div>
  );
}
