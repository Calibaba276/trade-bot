import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
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

export function SignUp() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const ngtTime = useNgtTime();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
    setTimeout(() => navigate("/sign-in"), 3000);
  };

  return (
    <div className="min-h-screen bg-[#0f1419] flex items-center justify-center px-4">
      <div className="w-full max-w-[360px]">
        {/* Back to landing */}
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-[#4b5563] hover:text-[#9ca3af] transition-colors mb-4"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
            <path d="M8 2L4 6L8 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back to home
        </Link>

        {/* Card */}
        <div
          className="bg-[#141921] p-8"
          style={{ border: "0.5px solid #2a3040" }}
        >
          {/* Signature: live system status */}
          <div
            className="font-mono text-[9px] uppercase tracking-wider pb-5 mb-6"
            style={{
              color: "#34d399",
              opacity: 0.55,
              borderBottom: "0.5px solid #1e2530",
            }}
          >
            GLASS BOX v2.1&nbsp;&nbsp;●&nbsp;&nbsp;ACCESS REQUEST&nbsp;&nbsp;●&nbsp;&nbsp;{ngtTime} NGT
          </div>

          {/* Wordmark */}
          <div className="mb-7">
            <p
              className="font-mono font-normal uppercase text-[#f3f4f6] mb-1"
              style={{ fontSize: "13px", letterSpacing: "0.3em" }}
            >
              GLASS BOX
            </p>
            <p className="font-mono text-[10px] text-[#6b7280]">
              Create your account
            </p>
          </div>

          {success ? (
            <div
              className="py-4 px-3 font-mono text-[10px] text-[#34d399]"
              style={{ border: "0.5px solid #34d399", background: "rgba(52,211,153,0.04)" }}
            >
              ACCOUNT CREATED — check your email to confirm.
              <br />
              <span className="text-[#6b7280]">Redirecting to login...</span>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div>
                <label
                  className="block font-mono uppercase text-[#6b7280] mb-1.5"
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
                  className="w-full bg-[#0f1419] font-mono text-[11px] text-[#f3f4f6] px-3 py-2.5 placeholder-[#4b5563] focus:outline-none transition-colors"
                  style={{ border: "0.5px solid #2a3040", borderRadius: 0 }}
                  onFocus={(e) => (e.target.style.borderColor = "#378add")}
                  onBlur={(e) => (e.target.style.borderColor = "#2a3040")}
                />
              </div>

              <div>
                <label
                  className="block font-mono uppercase text-[#6b7280] mb-1.5"
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
                  className="w-full bg-[#0f1419] font-mono text-[11px] text-[#f3f4f6] px-3 py-2.5 placeholder-[#4b5563] focus:outline-none transition-colors"
                  style={{ border: "0.5px solid #2a3040", borderRadius: 0 }}
                  onFocus={(e) => (e.target.style.borderColor = "#378add")}
                  onBlur={(e) => (e.target.style.borderColor = "#2a3040")}
                />
              </div>

              <div>
                <label
                  className="block font-mono uppercase text-[#6b7280] mb-1.5"
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
                  className="w-full bg-[#0f1419] font-mono text-[11px] text-[#f3f4f6] px-3 py-2.5 placeholder-[#4b5563] focus:outline-none transition-colors"
                  style={{ border: "0.5px solid #2a3040", borderRadius: 0 }}
                  onFocus={(e) => (e.target.style.borderColor = "#378add")}
                  onBlur={(e) => (e.target.style.borderColor = "#2a3040")}
                />
              </div>

              {error && (
                <p className="font-mono text-[10px] text-[#f87171] -mt-1">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-[#378add] hover:bg-[#2d74c8] font-mono text-[11px] uppercase text-white py-2.5 mt-1 transition-colors disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
                style={{ letterSpacing: "0.08em", borderRadius: 0, border: "none" }}
              >
                {loading ? "CREATING ACCOUNT..." : "CREATE ACCOUNT"}
              </button>
            </form>
          )}

          {/* Login link */}
          {!success && (
            <div
              className="mt-5 pt-5 font-mono text-[10px] text-[#6b7280]"
              style={{ borderTop: "0.5px solid #1e2530" }}
            >
              Already have an account?{" "}
              <Link
                to="/sign-in"
                className="text-[#9ca3af] hover:text-[#f3f4f6] underline transition-colors"
              >
                Sign in
              </Link>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-3 flex justify-between px-0.5 font-mono text-[9px] text-[#4b5563]">
          <span>© 2026 Glass Box</span>
          <span>All sessions logged</span>
        </div>
      </div>
    </div>
  );
}
