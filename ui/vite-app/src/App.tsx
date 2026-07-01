import { useEffect } from 'react';
import { HashRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { CommandPalette } from '@/features/commander/CommandPalette';
import { ToastContainer } from '@/components/Toast';
import { useSessionStore } from '@/store/sessionStore';
import { Login } from '@/features/auth/Login';
import GitHubCallbackPage from '@/pages/GitHubCallback';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('auth_token');
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

function MainApp() {
  const ensureSession = useSessionStore((s) => s.ensureSession);
  const initLlmFromStorage = useSessionStore((s) => s.initLlmFromStorage);
  const status = useSessionStore((s) => s.status);
  const sessionId = useSessionStore((s) => s.sessionId);
  const token = localStorage.getItem('auth_token');

  useEffect(() => {
    if (token && window.location.pathname !== '/login') {
      initLlmFromStorage();
      ensureSession();
    }
  }, [ensureSession, initLlmFromStorage, token]);

  if (token && status === 'connecting') {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-500 text-sm">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500/30 border-t-cyan-500" />
          <span>Syncing isolated workspace...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-sans">
      <DashboardLayout />
      <CommandPalette />
      <ToastContainer />
    </div>
  );
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/github/callback" element={<GitHubCallbackPage />} />
        <Route 
          path="/*" 
          element={
            <ProtectedRoute>
              <MainApp />
            </ProtectedRoute>
          } 
        />
      </Routes>
    </HashRouter>
  );
}
