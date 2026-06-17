import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

interface Props {
  open: boolean;
  /** Current wizard step (controlled — resumed from the user's saved progress). */
  step: number;
  /** Called when the user advances/goes back — persists progress across devices. */
  onStepChange: (step: number) => void;
  /** Called when onboarding is completed or skipped — persists the "done" flag. */
  onClose: () => void;
}

interface Step {
  badge: string;
  icon: string;
  title: string;
  body: string;
  bullets?: string[];
  cta: string;
}

const STEPS: Step[] = [
  {
    badge: "Welcome",
    icon: "⬡",
    title: "Welcome to Glass Box",
    body:
      "Glass Box runs an ICT-based trading engine on your behalf and shows you every decision it makes — the liquidity sweep, the entry, the stop, the target. No black box. You see exactly why each trade was taken.",
    cta: "Next",
  },
  {
    badge: "Plans",
    icon: "★",
    title: "Starter & Pro",
    body:
      "Starter runs the engine on a single MT5 account. Pro unlocks up to 10 accounts, the Prop Firm Panel with halt simulation and profit-target tracking, and priority signal delivery — ideal if you run challenges across multiple brokers.",
    bullets: [
      "Up to 10 MT5 accounts",
      "Prop Firm Panel & halt simulation",
      "Priority signal delivery",
    ],
    cta: "Next",
  },
  {
    badge: "Get Started",
    icon: "🔌",
    title: "Connect your MT5 account",
    body:
      "To start executing signals, connect a MetaTrader 5 account. Your credentials are stored securely in Azure Key Vault and the engine begins scanning by the next session.",
    cta: "Connect MT5 account",
  },
];

export function OnboardingModal({ open, step, onStepChange, onClose }: Props) {
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  // Guard against an out-of-range saved step (e.g. after the wizard is shortened).
  const safeStep = Math.min(Math.max(step, 0), STEPS.length - 1);
  const current = STEPS[safeStep];
  const isLast = safeStep === STEPS.length - 1;

  const handleNext = () => {
    if (isLast) {
      onClose();
      navigate("/dashboard/settings");
      return;
    }
    onStepChange(safeStep + 1);
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-md"
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to Glass Box"
    >
      <div className="w-full max-w-md bg-bg-overlay border border-border-muted rounded-xl p-7 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <span className="font-mono text-[10px] uppercase tracking-wider text-brand-blue">
            {current.badge}
          </span>
          <button
            onClick={onClose}
            aria-label="Skip onboarding"
            className="text-text-muted hover:text-text-primary text-sm"
          >
            Skip
          </button>
        </div>

        {/* Icon */}
        <div className="h-12 w-12 rounded-lg bg-brand-blue/10 border border-brand-blue/30 flex items-center justify-center text-2xl text-brand-blue mb-4">
          <span aria-hidden>{current.icon}</span>
        </div>

        {/* Content */}
        <h2 className="text-lg font-display font-semibold text-text-primary mb-2">
          {current.title}
        </h2>
        <p className="text-sm text-text-secondary leading-relaxed">{current.body}</p>

        {current.bullets && (
          <ul className="mt-4 space-y-1.5 text-xs text-text-secondary">
            {current.bullets.map((b) => (
              <li key={b} className="flex gap-2">
                <span className="text-bull shrink-0" aria-hidden>✓</span>
                {b}
              </li>
            ))}
          </ul>
        )}

        {/* Footer */}
        <div className="mt-7 flex items-center justify-between">
          {/* Step dots */}
          <div className="flex items-center gap-1.5" aria-hidden>
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`h-1.5 rounded-full transition-all ${
                  i === safeStep ? "w-5 bg-brand-blue" : "w-1.5 bg-border-muted"
                }`}
              />
            ))}
          </div>

          <div className="flex items-center gap-2">
            {safeStep > 0 && (
              <button
                onClick={() => onStepChange(safeStep - 1)}
                className="text-sm text-text-secondary hover:text-text-primary px-3 py-2"
              >
                Back
              </button>
            )}
            <button
              onClick={handleNext}
              className="text-sm bg-brand-blue hover:bg-brand-dim text-white rounded-md px-4 py-2"
            >
              {current.cta}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
