import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { adminApi } from '../../api/admin';
import { useFetch } from '../../hooks/useFetch';
import AsyncButton from '../../components/ui/AsyncButton';
import Skeleton from '../../components/ui/Skeleton';
import { timeAgo } from '../../utils/formatters';

const ROLE = { nurse: 'Nurse', clinician: 'Clinical officer', admin: 'Administrator' };
const schema = z.object({
  username: z.string().regex(/^[A-Za-z0-9_.-]{3,50}$/, 'Use 3 to 50 letters, numbers, dots, dashes or underscores'),
  email: z.string().email('Enter a valid email address'),
  role: z.enum(['nurse', 'clinician', 'admin']),
  password: z.string().min(12, 'Use at least 12 characters'),
});

function CreateAccount({ onCreated }) {
  const [msg, setMsg] = useState(null);
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema), defaultValues: { role: 'nurse' } });
  const submit = async (v) => {
    setMsg(null);
    try {
      await adminApi.createUser(v);
      reset({ role: 'nurse' });
      setMsg({ ok: true, text: `Account ${v.username} created. Give them the password in person.` });
      onCreated();
    } catch (e) {
      setMsg({ ok: false, text: e.response?.data?.detail && typeof e.response.data.detail === 'string' ? e.response.data.detail : 'Could not create the account. Check the details and try again.' });
    }
  };
  const field = 'mt-1 min-h-[44px] w-full rounded-lg border border-slate-400 px-3 text-base';
  const err = (k) => errors[k] && <p className="mt-1 text-sm text-red-700">{errors[k].message}</p>;
  return (
    <form onSubmit={handleSubmit(submit)} noValidate className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-3 font-semibold">Create a staff account</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-sm">Username<input className={field} {...register('username')} />{err('username')}</label>
        <label className="text-sm">Email<input className={field} {...register('email')} />{err('email')}</label>
        <label className="text-sm">Role
          <select className={field} {...register('role')}>{Object.entries(ROLE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </label>
        <label className="text-sm">Temporary password<input type="password" autoComplete="new-password" className={field} {...register('password')} />{err('password')}</label>
      </div>
      {msg && <p role={msg.ok ? 'status' : 'alert'} className={`mt-3 text-sm ${msg.ok ? 'text-green-800' : 'text-red-700'}`}>{msg.text}</p>}
      <button disabled={isSubmitting} className="mt-4 min-h-[44px] rounded-lg bg-brand px-4 font-semibold text-white disabled:opacity-60">{isSubmitting ? 'Creating…' : 'Create account'}</button>
    </form>
  );
}

export default function UsersPage() {
  const { data: users, loading, error, refetch } = useFetch(() => adminApi.getUsers());
  const act = (id, action) => async () => { await adminApi.userAction(id, action); await refetch(); };
  const th = 'px-3 py-2 font-medium';
  const pending = (users ?? []).filter((u) => u.status === 'pending');
  const staff = (users ?? []).filter((u) => ['active', 'disabled'].includes(u.status));

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Users</h1>
      <CreateAccount onCreated={refetch} />

      {loading ? <Skeleton rows={3} /> : error?.notSupported ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
          <h2 className="mb-1 font-semibold text-slate-900">Staff list and approvals</h2>
          The server cannot list staff accounts or approve access requests yet. It needs <code>GET /auth/users</code> and <code>PATCH /auth/users/{'{id}'}</code>, plus <code>POST /auth/request-access</code> so staff can request their own account. Until then, create accounts here.
        </div>
      ) : error ? (
        <div role="alert" className="rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          Could not load staff accounts.
          <button onClick={refetch} className="ml-3 rounded-lg border border-amber-600 px-3 py-1 font-semibold">Try again</button>
        </div>
      ) : (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-1 font-semibold">Pending requests ({pending.length})</h2>
            <p className="mb-3 text-sm text-slate-500">Staff cannot sign in until you approve their request.</p>
            {pending.length === 0 ? <p className="text-sm text-slate-500">No requests waiting.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead className="bg-slate-50 text-slate-600"><tr>{['Username', 'Email', 'Role', 'Requested', 'Decision'].map((h) => <th scope="col" key={h} className={th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {pending.map((u) => (
                      <tr key={u.id} className="border-t border-slate-100">
                        <td className="px-3 py-3 font-semibold">{u.username}</td>
                        <td className="px-3 py-3">{u.email}</td>
                        <td className="px-3 py-3">{ROLE[u.role]}</td>
                        <td className="px-3 py-3">{timeAgo(u.created_at)}</td>
                        <td className="px-3 py-3"><div className="flex gap-2">
                          <AsyncButton onClick={act(u.id, 'approve')} className="bg-brand text-white">Approve</AsyncButton>
                          <AsyncButton onClick={act(u.id, 'reject')} className="border border-red-300 text-red-700">Reject</AsyncButton>
                        </div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-3 font-semibold">Staff accounts</h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="bg-slate-50 text-slate-600"><tr>{['Username', 'Email', 'Role', 'Status', 'Action'].map((h) => <th scope="col" key={h} className={th}>{h}</th>)}</tr></thead>
                <tbody>
                  {staff.map((u) => (
                    <tr key={u.id} className={`border-t border-slate-100 ${u.status === 'disabled' ? 'text-slate-500' : ''}`}>
                      <td className="px-3 py-3 font-semibold">{u.username}</td>
                      <td className="px-3 py-3">{u.email}</td>
                      <td className="px-3 py-3">{ROLE[u.role]}</td>
                      <td className="px-3 py-3">{u.status === 'active' ? 'Active' : 'Disabled'}</td>
                      <td className="px-3 py-3">
                        {u.role !== 'admin' && (u.status === 'active'
                          ? <AsyncButton onClick={act(u.id, 'disable')} className="border border-slate-300">Disable</AsyncButton>
                          : <AsyncButton onClick={act(u.id, 'enable')} className="border border-slate-300">Enable</AsyncButton>)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
