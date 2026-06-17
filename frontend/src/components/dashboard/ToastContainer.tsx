import { useEffect, useRef } from "react";
import { useToastStore, type Toast, type ToastVariant } from "../../store/toastStore";

const VARIANT_STYLES: Record<ToastVariant, { bar: string; icon: string; glyph: string }> = {
  info:     { bar: "bg-brand-blue",   icon: "text-brand-blue",   glyph: "ℹ" },
  success:  { bar: "bg-bull",         icon: "text-bull",         glyph: "✓" },
  warning:  { bar: "bg-amber",        icon: "text-amber",        glyph: "⚠" },
  critical: { bar: "bg-bear",         icon: "text-bear",         glyph: "✕" },
};

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss);
  const { bar, icon, glyph } = VARIANT_STYLES[toast.variant];
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const duration = toast.durationMs ?? 6000;
    if (barRef.current) {
      barRef.current.style.transition = `width ${duration}ms linear`;
      requestAnimationFrame(() => {
        if (barRef.current) barRef.current.style.width = "0%";
      });
    }
    const timer = setTimeout(() => dismiss(toast.id), duration);
    return () => clearTimeout(timer);
  }, [toast.id, toast.durationMs, dismiss]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="relative flex items-start gap-3 w-80 bg-bg-overlay border border-border-muted rounded-lg shadow-xl overflow-hidden"
    >
      {/* Left accent bar */}
      <div className={`absolute left-0 top-0 bottom-0 w-0.5 ${bar}`} />

      <div className="flex items-start gap-3 px-4 py-3 pr-8 w-full">
        <span className={`mt-0.5 text-sm shrink-0 ${icon}`} aria-hidden>{glyph}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-text-primary leading-snug">{toast.title}</p>
          {toast.body && (
            <p className="text-xs text-text-muted mt-0.5 leading-snug">{toast.body}</p>
          )}
        </div>
      </div>

      {/* Dismiss button */}
      <button
        onClick={() => dismiss(toast.id)}
        className="absolute top-2 right-2 text-text-muted hover:text-text-primary transition-colors"
        aria-label="Dismiss notification"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
          <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      </button>

      {/* Progress bar — shrinks from full → 0 over durationMs */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-border-subtle">
        <div ref={barRef} className={`h-full w-full ${bar} opacity-60`} />
      </div>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-label="Notifications"
      className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto animate-slide-in">
          <ToastItem toast={t} />
        </div>
      ))}
    </div>
  );
}
