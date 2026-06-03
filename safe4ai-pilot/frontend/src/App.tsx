import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import ErrorBoundary from "./components/ErrorBoundary";
import ChatPage from "./pages/ChatPage";
import LoginPage from "./pages/LoginPage";
import ActivityPage from "./pages/admin/ActivityPage";
import DocumentsPage from "./pages/admin/DocumentsPage";
import FeedbackPage from "./pages/admin/FeedbackPage";
import OverviewPage from "./pages/admin/OverviewPage";
import UsersPage from "./pages/admin/UsersPage";
import SettingsPage from "./pages/admin/SettingsPage";
import UserSettingsPage from "./pages/SettingsPage";

function AuthLoading() {
  return (
    <div className="flex h-screen items-center justify-center bg-paper">
      <span className="text-[13px] text-text-mute">Loading…</span>
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <AuthLoading />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { isAdmin, isLoading } = useAuth();
  if (isLoading) return <AuthLoading />;
  if (!isAdmin) return <Navigate to="/chat" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

      <Route
        path="/chat"
        element={
          <RequireAuth>
            <ChatPage />
          </RequireAuth>
        }
      />

      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <Navigate to="/admin/overview" replace />
          </RequireAdmin>
        }
      />
      <Route
        path="/admin/overview"
        element={
          <RequireAdmin>
            <OverviewPage />
          </RequireAdmin>
        }
      />
      <Route
        path="/admin/documents"
        element={
          <RequireAdmin>
            <DocumentsPage />
          </RequireAdmin>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <RequireAdmin>
            <ActivityPage />
          </RequireAdmin>
        }
      />
      <Route
        path="/admin/feedback"
        element={
          <RequireAdmin>
            <FeedbackPage />
          </RequireAdmin>
        }
      />
      <Route
        path="/admin/users"
        element={
          <RequireAdmin>
            <UsersPage />
          </RequireAdmin>
        }
      />

      <Route
        path="/admin/settings"
        element={
          <RequireAdmin>
            <SettingsPage />
          </RequireAdmin>
        }
      />

      <Route
        path="/settings"
        element={
          <RequireAuth>
            <UserSettingsPage />
          </RequireAuth>
        }
      />

        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
