import { useAuthStore } from '../../store/authStore';

const ROLE = { nurse: 'Nurse', clinician: 'Clinical officer', admin: 'Administrator' };

export default function ProfilePage() {
  const { user, logout } = useAuthStore();
  return (
    <div className="max-w-md">
      <h1 className="mb-4 text-2xl font-bold">Profile</h1>
      <dl className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 text-sm">
        <div><dt className="text-slate-500">Username</dt><dd className="font-semibold">{user?.username ?? '—'}</dd></div>
        {user?.email && <div><dt className="text-slate-500">Email</dt><dd className="font-semibold">{user.email}</dd></div>}
        <div><dt className="text-slate-500">Role</dt><dd className="font-semibold">{ROLE[user?.role] ?? user?.role}</dd></div>
      </dl>
      <p className="mt-3 text-sm text-slate-500">To change your password or role, ask an administrator.</p>
      <button onClick={logout} className="mt-4 min-h-[44px] rounded-lg border border-slate-300 bg-white px-4">Sign out</button>
    </div>
  );
}
