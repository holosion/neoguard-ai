import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './Sidebar';
import { useAlertStore } from '../../store/alertStore';
import { POLL_INTERVAL_MS } from '../../utils/constants';
import { tokenExpiry } from '../../utils/token';
import { useAuthStore } from '../../store/authStore';

export default function Layout({ role }) {
  const actualRole = useAuthStore((s) => s.user?.role);
  const [open, setOpen] = useState(false);
  const [minsLeft, setMinsLeft] = useState(null);
  const refresh = useAlertStore((s) => s.refresh);

  // Keeps the alerts badge and Alerts page current while signed in.
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  // Warns when the sign-in is about to end, so staff are not logged out without notice.
  useEffect(() => {
    const check = () => {
      const exp = tokenExpiry();
      setMinsLeft(exp ? Math.ceil((exp - Date.now()) / 60000) : null);
    };
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex min-h-screen">
      {open && <div className="fixed inset-0 z-10 bg-black/40 md:hidden" onClick={() => setOpen(false)} aria-hidden="true" />}
      <Sidebar role={actualRole ?? role} open={open} onClose={() => setOpen(false)} />
      <div className="min-w-0 flex-1">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <button onClick={() => setOpen(true)} aria-label="Open menu" className="rounded-lg border border-slate-300 p-2">
            <Menu size={20} />
          </button>
          <span className="font-bold text-brand">Neonatal Monitor</span>
        </header>
        {minsLeft !== null && minsLeft > 0 && minsLeft <= 5 && (
          <div role="status" className="border-b border-amber-400 bg-amber-50 px-4 py-2 text-sm text-amber-900 md:px-7">
            Your sign-in ends in {minsLeft} min. Sign out and sign in again soon to avoid being interrupted.
          </div>
        )}
        <main className="p-4 md:p-7">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
