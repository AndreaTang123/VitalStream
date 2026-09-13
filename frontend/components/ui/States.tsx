import { clsx } from "clsx";
import { Button } from "./Button";

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-md bg-slate-800", className)} />;
}

export function CardSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-5/6" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-md border border-dashed border-border p-6 text-center">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted">{description}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-md border border-danger/30 bg-danger/10 p-4">
      <p className="text-sm text-red-300">{message}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function ForbiddenState({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-warning/30 bg-warning/10 p-6 text-center">
      <p className="text-sm font-medium text-amber-300">Access denied</p>
      <p className="mt-1 text-sm text-muted">{message}</p>
    </div>
  );
}
