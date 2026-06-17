import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { Landing } from "./pages/Landing";
import { Login } from "./components/Auth/Login";
import { SignUp } from "./components/Auth/SignUp";
import { SharePage } from "./pages/SharePage";
import { DashboardLayout } from "./components/dashboard/DashboardLayout";
import { Overview } from "./pages/dashboard/Overview";
import { FeedPage } from "./pages/dashboard/FeedPage";
import { ChartPage } from "./pages/dashboard/ChartPage";
import { TradesPage } from "./pages/dashboard/TradesPage";
import { PropFirmPage } from "./pages/dashboard/PropFirmPage";
import { SettingsPage } from "./pages/dashboard/SettingsPage";
import { ProGuard } from "./components/dashboard/ProGuard";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-bg-base" />;
  return user ? <>{children}</> : <Navigate to="/sign-in" replace />;
}

export default function App() {
  return (
    <Routes>
      {/* Public marketing */}
      <Route path="/" element={<Landing />} />

      {/* Auth (spec routes + legacy aliases) */}
      <Route path="/sign-in" element={<Login />} />
      <Route path="/sign-up" element={<SignUp />} />
      <Route path="/login" element={<Navigate to="/sign-in" replace />} />
      <Route path="/signup" element={<Navigate to="/sign-up" replace />} />

      {/* Public shareable audit link — no auth required */}
      <Route path="/share/:token" element={<SharePage />} />

      {/* Protected dashboard app */}
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <DashboardLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<Overview />} />
        <Route path="feed" element={<FeedPage />} />
        <Route
          path="chart"
          element={
            <ProGuard
              feature="replayMode"
              title="Replay Mode"
              blurb="Step through historical price action candle-by-candle and watch the engine's reasoning unfold. Available on the Pro plan."
            >
              <ChartPage />
            </ProGuard>
          }
        />
        <Route path="trades" element={<TradesPage />} />
        <Route
          path="propfirm"
          element={
            <ProGuard
              feature="propFirmPanel"
              title="Prop Firm Panel"
              blurb="Track daily drawdown, consecutive-loss limits, halt simulation and profit-target progress against your prop firm's rules. Available on the Pro plan."
            >
              <PropFirmPage />
            </ProGuard>
          }
        />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
