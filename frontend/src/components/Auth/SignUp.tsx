import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { signUp } from "../../lib/supaclient";

function useNgtTime() {
  const getNgt = () => {
    const ngt = new Date(Date.now() + 60 * 60 * 1000);
    return ngt.toUTCString().slice(17, 25);
  };
  const [time, setTime] = useState(getNgt);
  useEffect(() => {
    const id = setInterval(() => setTime(getNgt()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

function getTradingSession(): string {
  const ngtHour = (new Date().getUTCHours() + 1) % 24;
  if (ngtHour >= 1 && ngtHour < 7) return "ASIAN SESSION";
  if (ngtHour >= 7 && ngtHour < 9) return "PRE-LONDON";
  if (ngtHour >= 9 && ngtHour < 11) return "LONDON SESSION";
  if (ngtHour >= 11 && ngtHour < 13) return "OVERLAP";
  if (ngtHour >= 13 && ngtHour < 17) return "NY SESSION";
  return "OFF-HOURS";
}

export function SignUp() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const ngtTime = useNgtTime();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    setError(null);

    const { error } = await signUp(email, password);
    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    setSuccess(true);
  };

  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center px-4">
      <div className="w-full max-w-[360px]">
        {/* Back to landing */}
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-text-muted hover:text-text-secondary transition-colors mb-4"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
            <path d="M8 2L4 6L8 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back to home
        </Link>

        {/* Card */}
        <div className="bg-bg-surface p-8 border-[0.5px] border-border-muted">
          {/* Signature: live system status */}
          <div className="font-mono text-[9px] uppercase tracking-wider pb-5 mb-6 text-bull opacity-[0.55] border-b-[0.5px] border-border-subtle">
            GLASS BOX v2.1&nbsp;&nbsp;●&nbsp;&nbsp;{getTradingSession()}&nbsp;&nbsp;●&nbsp;&nbsp;{ngtTime} NGT
          </div>

          {/* Wordmark */}
          <div className="mb-7">
            <p
              className="font-mono font-normal uppercase text-text-primary mb-1"
              style={{ fontSize: "13px", letterSpacing: "0.3em" }}
            >
              GLASS BOX
            </p>
            <p className="font-mono text-[10px] text-text-secondary">
              Create your account
            </p>
          </div>

          {success ? (
            <div className="py-4 px-3 font-mono text-[10px] text-bull border-[0.5px] border-bull bg-[rgba(63,185,80,0.04)]">
              ACCOUNT CREATED — check your email to confirm.
              <br />
              <span className="text-text-secondary">
                The confirmation link takes you straight to your dashboard.
              </span>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div>
                <label
                  className="block font-mono uppercase text-text-secondary mb-1.5"
                  style={{ fontSize: "9px", letterSpacing: "0.1em" }}
                >
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  placeholder="trader@firm.com"
                  className="w-full bg-bg-base font-mono text-[11px] text-text-primary px-3 py-2.5 placeholder-text-muted border-[0.5px] border-border-muted rounded-none focus:outline-none focus:border-border-active transition-colors"
                />
              </div>

              <div>
                <label
                  className="block font-mono uppercase text-text-secondary mb-1.5"
                  style={{ fontSize: "9px", letterSpacing: "0.1em" }}
                >
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  placeholder="••••••••"
                  className="w-full bg-bg-base font-mono text-[11px] text-text-primary px-3 py-2.5 placeholder-text-muted border-[0.5px] border-border-muted rounded-none focus:outline-none focus:border-border-active transition-colors"
                />
                <p className="mt-1.5 font-mono text-[9px] text-text-muted">
                  At least 6 characters
                </p>
              </div>

              <div>
                <label
                  className="block font-mono uppercase text-text-secondary mb-1.5"
                  style={{ fontSize: "9px", letterSpacing: "0.1em" }}
                >
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  autoComplete="new-password"
                  placeholder="••••••••"
                  className="w-full bg-bg-base font-mono text-[11px] text-text-primary px-3 py-2.5 placeholder-text-muted border-[0.5px] border-border-muted rounded-none focus:outline-none focus:border-border-active transition-colors"
                />
              </div>

              {error && (
                <p className="font-mono text-[10px] text-bear -mt-1">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-brand-blue hover:bg-brand-dim font-mono text-[11px] tracking-[0.08em] uppercase text-white py-2.5 mt-1 rounded-none border-0 transition-colors disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
              >
                {loading ? "CREATING ACCOUNT..." : "CREATE ACCOUNT"}
              </button>
            </form>
          )}

          {/* Login link */}
          {!success && (
            <div className="mt-5 pt-5 font-mono text-[10px] text-text-secondary border-t-[0.5px] border-border-subtle">
              Already have an account?{" "}
              <Link
                to="/sign-in"
                className="text-text-secondary hover:text-text-primary underline transition-colors"
              >
                Sign in
              </Link>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-3 flex justify-between px-0.5 font-mono text-[9px] text-text-muted">
          <span>© 2026 Glass Box</span>
          <span>All sessions logged</span>
        </div>
      </div>
    </div>
  );
}
