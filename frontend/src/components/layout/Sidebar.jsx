import { NavLink } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { useAlertStore, selectUnacknowledged } from '../../store/alertStore';

const NURSE_NAV = [
  { to: '/', label: 'Triage', end: true },
  { to: '/patients', label: 'Patients' },
  { to: '/alerts', label: 'Alerts', badge: true },
  { to: '/devices', label: 'Devices' },
  { to: '/profile', label: 'Profile' },
];
const ADMIN_NAV = [
  { to: '/admin', label: 'Overview', end: true },
  { to: '/admin/devices', label: 'Devices' },
  { to: '/admin/patients', label: 'Patients' },
  { to: '/admin/sessions', label: 'Sessions' },
  { to: '/admin/alerts', label: 'Alerts' },
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/settings', label: 'Settings' },
];

export default function Sidebar({ role, open, onClose }) {
  const { user, logout } = useAuthStore();
  const unack = useAlertStore(selectUnacknowledged);
  const items = role === 'admin' ? ADMIN_NAV : NURSE_NAV;
  return (
    <aside className={`${open ? 'flex' : 'hidden'} fixed inset-y-0 left-0 z-20 w-56 flex-col bg-navy p-3 text-slate-300 md:static md:flex`}>
      <div className="px-2 pb-5 pt-2 text-base font-bold text-white">
        Neonatal Monitor
        {role === 'admin' && <div className="text-xs font-normal text-slate-400">Administration</div>}
      </div>
      <nav aria-label="Main" className="flex flex-col gap-1">
        {items.map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            end={i.end}
            onClick={onClose}
            className={({ isActive }) =>
              `flex min-h-[44px] items-center justify-between rounded-lg px-3 ${isActive ? 'bg-slate-700 font-semibold text-white' : 'hover:bg-slate-800'}`
            }
          >
            {i.label}
            {i.badge && unack > 0 ? <span className="rounded-full bg-red-600 px-2 text-xs text-white" ><span aria-hidden="true">{unack}</span><span className="sr-only">{unack} unacknowledged alerts</span></span> : null}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto border-t border-slate-700 pt-3 text-sm">
        <div className="text-white">{user?.username ?? user?.name ?? 'Signed in'}</div>
        <div className="text-slate-400">{role === 'admin' ? 'Administrator' : 'Nurse'}</div>
        <button onClick={logout} className="mt-2 w-full rounded-lg border border-slate-600 py-2 hover:bg-slate-800">Sign out</button>
      </div>
    </aside>
  );
}
