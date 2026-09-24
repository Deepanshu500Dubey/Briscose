import { Button } from './Button';

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-line-soft ${className}`} />;
}

export function SkeletonRows({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className="h-14 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  action,
}: {
  title: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-line py-10 text-center">
      <p className="text-sm text-ink-soft">{title}</p>
      {action && (
        <Button variant="outline" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-status-bad-line bg-status-bad-bg py-8 text-center">
      <p className="text-sm text-status-bad-fg">{message}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** Stale-while-revalidate (project blueprint, Section 12): when a
 * background refetch fails but we still have last-good data to show,
 * don't blank the screen — keep the stale data visible with a small inline
 * retry banner instead of a full-screen ErrorState. */
export function StaleDataBanner({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="mb-3 flex items-center justify-between rounded-lg border border-status-warn-line bg-status-warn-bg px-4 py-2 text-sm text-status-warn-fg">
      <span>Showing the last data we loaded — the latest refresh failed.</span>
      <Button variant="outline" onClick={onRetry} className="border-status-warn-line">
        Retry
      </Button>
    </div>
  );
}
