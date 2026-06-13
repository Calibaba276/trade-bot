import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";

// Pages — stubs until Phase 1.4 + Phase 2
const Login = () => (
  <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
    Login page — coming in Phase 1.4
  </div>
);
const Dashboard = () => (
  <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
    Dashboard — coming in Phase 2
  </div>
);

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-gray-900" />;
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Dashboard />
          </PrivateRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
