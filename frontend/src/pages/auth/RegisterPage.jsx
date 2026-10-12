import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { useFetch } from '../../hooks/useFetch';

const schema = z.object({
  username: z.string().regex(/^[A-Za-z0-9_.-]{3,50}$/, 'Use 3 to 50 letters, numbers, dots, dashes or underscores'),
  email: z.string().email('Enter a valid work email'),
  role: z.enum(['nurse', 'clinician']),
  clinic_id: z.string().min(1, 'Choose your clinic'),
  password: z.string().min(12, 'Use at least 12 characters'),
  confirm: z.string(),
}).refine((v) => v.password === v.confirm, { path: ['confirm'], message: 'Passwords do not match' });

export default function RegisterPage() {
  const [sent, setSent] = useState(false);
  const [formError, setFormError] = useState(null);
  const { data: clinics, loading: clinicsLoading } = useFetch(() => authApi.clinics());
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema), defaultValues: { role: 'nurse' } });

  const onSubmit = async ({ confirm, clinic_id, ...body }) => {
    setFormError(null);
    try { await authApi.requestAccess({ ...body, clinic_id: Number(clinic_id) }); setSent(true); } catch (e) {
      const detail = e.response?.data?.detail;
      setFormError(typeof detail === 'string' ? detail : 'Could not send your request. Check your details and connection, then try again.');
    }
  };

  const field = 'mt-1 min-h-[44px] w-full rounded-lg border border-slate-400 px-3 text-base';
  const err = (k) => errors[k] && <p className="mt-1 text-sm text-red-700">{errors[k].message}</p>;

  if (sent) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8">
          <h1 className="text-xl font-bold text-brand">Request sent</h1>
          <p className="mt-2 text-sm text-slate-600">An administrator must approve your account before you can sign in.</p>
          <Link to="/login" className="mt-6 block min-h-[44px] rounded-lg bg-brand py-3 text-center font-semibold text-white">Back to sign in</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8">
        <h1 className="text-xl font-bold text-brand">Request staff access</h1>
        <p className="mb-5 text-sm text-slate-500">For nurses and clinical officers</p>
        <label className="block text-sm">Username<input className={field} autoComplete="username" {...register('username')} /></label>{err('username')}
        <label className="mt-3 block text-sm">Work email<input className={field} autoComplete="email" {...register('email')} /></label>{err('email')}
        <label className="mt-3 block text-sm">Role
          <select className={field} {...register('role')}><option value="nurse">Nurse</option><option value="clinician">Clinical officer</option></select>
        </label>
        <label className="mt-3 block text-sm">Clinic
          <select className={field} {...register('clinic_id')}><option value="">{clinicsLoading ? 'Loading clinics…' : 'Choose your clinic'}</option>{clinics?.map((clinic) => <option key={clinic.id} value={clinic.id}>{clinic.name}</option>)}</select>
        </label>{err('clinic_id')}
        <label className="mt-3 block text-sm">Password<input type="password" autoComplete="new-password" className={field} {...register('password')} /></label>{err('password')}
        <label className="mt-3 block text-sm">Confirm password<input type="password" autoComplete="new-password" className={field} {...register('confirm')} /></label>{err('confirm')}
        {formError && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{formError}</p>}
        <button disabled={isSubmitting || clinicsLoading || !clinics?.length} className="mt-6 min-h-[48px] w-full rounded-lg bg-brand font-semibold text-white disabled:opacity-60">{isSubmitting ? 'Sending…' : 'Submit request'}</button>
        <p className="mt-3 text-xs text-slate-500">An administrator must approve your account before you can sign in.</p>
        <Link to="/login" className="mt-3 inline-block text-sm font-semibold text-brand">Back to sign in</Link>
      </form>
    </div>
  );
}
