"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";

/**
 * Step 8: "回滚必须有二次确认对话框" — the whole reason this component
 * exists is that one line. A native `confirm()` would satisfy the letter of
 * it but reads as an afterthought in a demo recording.
 */
export function useConfirm() {
  const [pending, setPending] = useState<{ message: string; onConfirm: () => void } | null>(null);

  function confirm(message: string, onConfirm: () => void) {
    setPending({ message, onConfirm });
  }

  const dialog = pending && (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-sm rounded-lg border border-border bg-surface p-5 shadow-xl">
        <p className="text-sm text-foreground">{pending.message}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setPending(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              pending.onConfirm();
              setPending(null);
            }}
          >
            Confirm
          </Button>
        </div>
      </div>
    </div>
  );

  return { confirm, dialog };
}
