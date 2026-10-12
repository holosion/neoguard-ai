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
  role: z.enum(['nurse', 'clinician']),
  clinic_id: z.string().min(1, 'Choose a clinic'),
  password: z.string().min(12, 'Use at least 12 characters'),
});

function CreateAccount({ clinics, onCreated }) {
  const [msg, setMsg] = useState(null);
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema), defaultValues: { role: 'nurse' } });
  const submit = async (v) => {
    setMsg(null);
    try {
      await adminApi.createUser({ ...v, clinic_id: Number(v.clinic_id) });
      reset({ role: 'nurse', clinic_id: '' });
      setMsg({ ok: true, text: `Account ${v.username} created.` });
      onCreated();
    } catch (e) {
      setMsg({ ok: false, text: e.response?.data?.detail ?? 'Could not create the account. Check the details and try again.' });
    }
  };
  const field = 'mt-1 min-h-[44px] w-full rounded-lg border border-slate-400 px-3 text-base';
  const err = (k) => errors[k] && <p className="mt-1 text-sm text-red-700">{errors[k].message}</p>;
  return (
    <form onSubmit={handleSubmit(submit)} noValidate className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-3 font-semibold">Create a staff account</h2>
      {!clinics?.length && <p className="mb-3 text-sm text-amber-800">Create an active clinic before adding staff.</p>}
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-sm">Username<input className={field} {...register('username')} />{err('username')}</label>
        <label className="text-sm">Email<input className={field} {...register('email')} />{err('email')}</label>
        <label className="text-sm">Clinic<select className={field} {...register('clinic_id')}><option value="">Choose a clinic</option>{clinics?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>{err('clinic_id')}</label>
        <label className="text-sm">Role<select className={field} {...register('role')}><option value="nurse">Nurse</option><option value="clinician">Clinical officer</option></select></label>
        <label className="text-sm">Temporary password<input type="password" autoComplete="new-password" className={field} {...register('password')} />{err('password')}</label>
      </div>
      {msg && <p role={msg.ok ? 'status' : 'alert'} className={`mt-3 text-sm ${msg.ok ? 'text-green-800' : 'text-red-700'}`}>{msg.text}</p>}
      <button disabled={isSubmitting || !clinics?.length} className="mt-4 min-h-[44px] rounded-lg bg-brand px-4 font-semibold text-white disabled:opacity-60">{isSubmitting ? 'Creating…' : 'Create account'}</button>
    </form>
  );
}

function CreateClinic({ onCreated }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true); setMessage(null);
    try { await adminApi.createClinic({ name: name.trim(), code: code.trim() }); setName(''); setCode(''); setMessage('Clinic created.'); onCreated(); }
    catch (error) { setMessage(error.response?.data?.detail ?? 'Could not create the clinic.'); }
    finally { setBusy(false); }
  };
  const field = 'mt-1 min-h-[44px] w-full rounded-lg border border-slate-400 px-3 text-base';
  return <form onSubmit={submit} className="rounded-xl border border-slate-200 bg-white p-4"><h2 className="mb-3 font-semibold">Add a clinic</h2><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Clinic name<input required minLength={2} maxLength={120} value={name} onChange={(e) => setName(e.target.value)} className={field} /></label><label className="text-sm">Clinic code<input required minLength={2} maxLength={40} pattern="[A-Za-z0-9_-]+" value={code} onChange={(e) => setCode(e.target.value)} className={field} /></label></div>{message && <p role="status" className="mt-2 text-sm text-slate-700">{message}</p>}<button disabled={busy} className="mt-3 min-h-[40px] rounded-lg bg-brand px-4 font-semibold text-white disabled:opacity-60">{busy ? 'Saving…' : 'Add clinic'}</button></form>;
}

export default function UsersPage() {
  const users = useFetch(() => adminApi.getUsers());
  const requests = useFetch(() => adminApi.getAccessRequests());
  const clinics = useFetch(() => adminApi.getClinics());
  const refetch = () => { users.refetch(); requests.refetch(); };
  const decide = (id, action) => async () => { await adminApi.decideAccessRequest(id, { action }); await requests.refetch(); if (action === 'approve') await users.refetch(); };
  const act = (id, action) => async () => { await adminApi.userAction(id, action); await users.refetch(); };
  const th = 'px-3 py-2 font-medium';
  const pending = requests.data ?? [];
  const staff = (users.data ?? []).filter((u) => ['active', 'disabled'].includes(u.status));

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Users</h1>
      <CreateClinic onCreated={clinics.refetch} />
      <CreateAccount clinics={clinics.data} onCreated={refetch} />
      {(users.error || requests.error || clinics.error) && <div role="alert" className="rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">Could not load all user management data. <button onClick={refetch} className="underline">Retry</button></div>}
      {requests.loading ? <Skeleton rows={3} /> : <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-1 font-semibold">Pending requests ({pending.length})</h2>
        <p className="mb-3 text-sm text-slate-500">Staff cannot sign in until an administrator approves their request.</p>
        {!pending.length ? <p className="text-sm text-slate-500">No requests waiting.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr>{['Username', 'Email', 'Clinic', 'Role', 'Requested', 'Decision'].map((h) => <th scope="col" key={h} className={th}>{h}</th>)}</tr></thead>
          <tbody>{pending.map((u) => <tr key={u.id} className="border-t border-slate-100"><td className="px-3 py-3 font-semibold">{u.username}</td><td className="px-3 py-3">{u.email}</td><td className="px-3 py-3">{clinics.data?.find((c) => c.id === u.clinic_id)?.name ?? `Clinic ${u.clinic_id}`}</td><td className="px-3 py-3">{ROLE[u.role]}</td><td className="px-3 py-3">{timeAgo(u.created_at)}</td><td className="px-3 py-3"><div className="flex gap-2"><AsyncButton onClick={decide(u.id, 'approve')} className="bg-brand text-white">Approve</AsyncButton><AsyncButton onClick={decide(u.id, 'reject')} className="border border-red-300 text-red-700">Reject</AsyncButton></div></td></tr>)}</tbody>
        </table></div>}
      </div>}
      {users.loading ? <Skeleton rows={3} /> : <div className="rounded-xl border border-slate-200 bg-white p-4"><h2 className="mb-3 font-semibold">Staff accounts</h2><div className="overflow-x-auto"><table className="w-full min-w-[640px] text-left text-sm">
        <thead className="bg-slate-50 text-slate-600"><tr>{['Username', 'Email', 'Clinic', 'Role', 'Status', 'Action'].map((h) => <th scope="col" key={h} className={th}>{h}</th>)}</tr></thead>
        <tbody>{staff.map((u) => <tr key={u.id} className={`border-t border-slate-100 ${u.status === 'disabled' ? 'text-slate-500' : ''}`}><td className="px-3 py-3 font-semibold">{u.username}</td><td className="px-3 py-3">{u.email}</td><td className="px-3 py-3">{clinics.data?.find((c) => c.id === u.clinic_id)?.name ?? '—'}</td><td className="px-3 py-3">{ROLE[u.role]}</td><td className="px-3 py-3">{u.status === 'active' ? 'Active' : 'Disabled'}</td><td className="px-3 py-3">{u.role !== 'admin' && (u.status === 'active' ? <AsyncButton onClick={act(u.id, 'disable')} className="border border-slate-300">Disable</AsyncButton> : <AsyncButton onClick={act(u.id, 'enable')} className="border border-slate-300">Enable</AsyncButton>)}</td></tr>)}</tbody>
      </table></div></div>}
    </div>
  );
}
