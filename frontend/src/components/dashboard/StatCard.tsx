import type { ReactNode } from "react";

interface Props {
  label: string;
  value: ReactNode;
  valueClass?: string;
  sub?: ReactNode;
  children?: ReactNode;
  /** When true, applies the data-flash animation to signal a live update. */
  flash?: boolean;
}

/** Reusable stat card per design guide §6.3. */
export function StatCard({ label, value, valueClass = "text-text-primary", sub, children, flash }: Props) {
  return (
    <div
      className={`bg-bg-surface border border-border-subtle rounded-lg p-4 ${flash ? "data-updated" : ""}`}
    >
      <p className="text-xs uppercase tracking-wide text-text-muted">{label}</p>
      <p className={`text-3xl font-mono font-bold mt-2 ${valueClass}`}>{value}</p>
      {sub && <div className="text-xs text-text-secondary mt-2">{sub}</div>}
      {children}
    </div>
  );
}
