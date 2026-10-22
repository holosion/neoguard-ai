import { Navigate, Route, Routes } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useAuthStore } from './store/authStore';
import { dashboardPreview } from './utils/preview';
import Layout from './components/layout/Layout';
import LoginPage from './pages/auth/LoginPage';
import ChangePasswordPage from './pages/auth/ChangePasswordPage';
import TriagePage from './pages/nurse/TriagePage';
import PatientDetailPage from './pages/nurse/PatientDetailPage';
import AlertsPage from './pages/nurse/AlertsPage';
import RegisterPage from './pages/auth/RegisterPage';
import OverviewPage from './pages/admin/OverviewPage';
import DevicesPage from './pages/admin/DevicesPage';
import DeviceDetailPage from './pages/admin/DeviceDetailPage';
import UsersPage from './pages/admin/UsersPage';
import PatientsPage from './pages/PatientsPage';
import NurseDevicesPage from './pages/nurse/DevicesPage';
import ProfilePage from './pages/nurse/ProfilePage';
import SessionsPage from './pages/admin/SessionsPage';
import SettingsPage from './pages/admin/SettingsPage';

// Redirects to /login if signed out, and blocks roles that are not allowed.
function Guard({ roles, children }) {
  const { isAuthenticated, mustChangePassword, user, fetchMe, logout } = useAuthStore();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!dashboardPreview && isAuthenticated && !user) fetchMe().then(() => setFailed(false), () => setFailed(true));
  }, [isAuthenticated, user, fetchMe]);
  if (dashboardPreview) return children;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (mustChangePassword) return <Navigate to="/change-password" replace />;
  if (failed) {
    return (
      <div role="alert" className="mx-auto mt-16 max-w-sm rounded-xl border border-amber-400 bg-amber-50 p-6 text-sm text-amber-900">
        Could not load your account. Check your connection.
        <div className="mt-4 flex gap-2">
          <button onClick={() => { setFailed(false); fetchMe().catch(() => setFailed(true)); }} className="rounded-lg border border-amber-600 px-3 py-2 font-semibold">Try again</button>
          <button onClick={logout} className="rounded-lg border border-slate-400 px-3 py-2">Sign out</button>
        </div>
      </div>
    );
  }
  if (!user) return <div className="p-8 text-slate-500">Loading…</div>;
  if (!roles.includes(user.role)) {
    return user.role === 'admin' ? <Navigate to="/admin" replace /> : <div className="p-8">You do not have access to this page (403).</div>;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={dashboardPreview ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />

      <Route element={<Guard roles={['nurse', 'clinician', 'admin']}><Layout role="nurse" /></Guard>}>
        <Route index element={<TriagePage />} />
        <Route path="patients" element={<PatientsPage />} />
        <Route path="patients/:id" element={<Guard roles={['nurse', 'clinician']}><PatientDetailPage /></Guard>} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="devices" element={<NurseDevicesPage />} />
        <Route path="profile" element={<ProfilePage />} />
      </Route>

      <Route path="/admin" element={<Guard roles={['admin']}><Layout role="admin" /></Guard>}>
        <Route index element={<OverviewPage />} />
        <Route path="devices" element={<DevicesPage />} />
        <Route path="devices/:id" element={<DeviceDetailPage />} />
        <Route path="patients" element={<PatientsPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
