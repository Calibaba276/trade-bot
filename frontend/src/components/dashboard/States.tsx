import type { ReactNode } from "react";

/** Full-bleed empty state (design guide §13). */
export function EmptyState({
  icon = "▢",
  title,
  body,
  action,
}: {
  icon?: string;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      <div className="text-4xl text-text-muted" aria-hidden>{icon}</div>
      <h3 className="text-base font-semibold text-text-primary mt-4">{title}</h3>
      <p className="text-sm text-text-secondary mt-1 max-w-sm">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Error state with retry. */
export function ErrorState({ title, body, onRetry }: { title: string; body: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      <div className="text-4xl text-bear" aria-hidden>⚠</div>
      <h3 className="text-base font-semibold text-text-primary mt-4">{title}</h3>
      <p className="text-sm text-text-secondary mt-1 max-w-sm">{body}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 rounded-md bg-brand-blue hover:bg-brand-dim text-white text-sm"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/** Simple shimmer skeleton block. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`bg-bg-elevated rounded animate-pulse ${className}`} />;
}
