import { useCallback, useEffect, useState } from "react";
import { supabase } from "../lib/supaclient";
import { useAuth } from "./useAuth";

/**
 * Account-scoped onboarding state, persisted in `public.user_onboarding`.
 *
 * Because the row is keyed by user_id (not device), a user who starts the
 * onboarding wizard on one device resumes at the same `step` on another.
 *
 * Completion is NOT triggered by clicking through the wizard — it is gated on
 * the user actually connecting a broker account. Until they do, the wizard
 * reappears on each visit (the final step deep-links them to settings). The
 * "Skip" / Escape affordance only dismisses it for the current session.
 */
export function useOnboarding() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [step, setStepState] = useState(0);

  const persist = useCallback(
    (next: { step?: number; completed?: boolean }) => {
      if (!user) return;
      supabase
        .from("user_onboarding")
        .upsert(
          { user_id: user.id, ...next, updated_at: new Date().toISOString() },
          { onConflict: "user_id" },
        )
        .then(({ error }) => {
          if (error) console.error("[useOnboarding] persist:", error.message);
        });
    },
    [user],
  );

  // Decide whether to show the wizard: completed users never see it; users with
  // a connected broker account are marked complete; everyone else resumes.
  useEffect(() => {
    let cancelled = false;
    if (!user) return;
    setLoading(true);

    Promise.all([
      supabase
        .from("user_onboarding")
        .select("step, completed")
        .eq("user_id", user.id)
        .maybeSingle(),
      supabase
        .from("broker_accounts")
        .select("id", { count: "exact", head: true })
        .eq("user_id", user.id),
    ]).then(([onboardingRes, accountsRes]) => {
      if (cancelled) return;

      // On error, fail closed (don't nag the user with the modal).
      if (onboardingRes.error || accountsRes.error) {
        setOpen(false);
        setLoading(false);
        return;
      }

      const row = onboardingRes.data;
      const hasAccount = (accountsRes.count ?? 0) > 0;
      setStepState(row?.step ?? 0);

      if (row?.completed) {
        setOpen(false);
      } else if (hasAccount) {
        // They've connected an account — onboarding is done. Record it so future
        // loads skip the broker_accounts check path.
        setOpen(false);
        persist({ completed: true });
      } else {
        setOpen(true);
      }
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [user, persist]);

  // Persist progress as the user moves through the wizard.
  const setStep = useCallback(
    (next: number) => {
      setStepState(next);
      persist({ step: next });
    },
    [persist],
  );

  // Soft dismiss — closes for this session but does NOT mark complete, so the
  // wizard returns until the user actually connects an account.
  const dismiss = useCallback(() => setOpen(false), []);

  return { loading, open, step, setStep, dismiss };
}
