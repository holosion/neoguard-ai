import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

const schema = z.object({
  username: z.string().min(1, 'Enter your username'),
  password: z.string().min(1, 'Enter your password'),
});

export default function LoginPage() {
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [formError, setFormError] = useState(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema) });

  const onSubmit = async ({ username, password }) => {
    setFormError(null);
    try {
      const user = await login(username, password);
      navigate(user.role === 'admin' ? '/admin' : '/', { replace: true });
    } catch (e) {
      if (e.response?.status === 429) {
        setFormError('Too many sign-in attempts. Wait 15 minutes and try again.');
        return;
      }
      setFormError('Sign in failed. Check your username and password, or ask an administrator if your account is approved.');
    }
  };

  const field = 'mt-1 min-h-[44px] w-full rounded-lg border border-slate-400 px-3 text-base';
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8" noValidate>
        <h1 className="text-xl font-bold text-brand">Neonatal Monitor</h1>
        <p className="mb-6 text-sm text-slate-500">Staff sign in</p>
        {params.get('expired') && <p role="status" className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Your sign-in expired. Sign in again to continue.</p>}
        <label className="block text-sm">Username
          <input className={field} autoComplete="username" {...register('username')} />
        </label>
        {errors.username && <p className="mt-1 text-sm text-red-700">{errors.username.message}</p>}
        <label className="mt-4 block text-sm">Password
          <input type="password" className={field} autoComplete="current-password" {...register('password')} />
        </label>
        {errors.password && <p className="mt-1 text-sm text-red-700">{errors.password.message}</p>}
        {formError && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{formError}</p>}
        <button disabled={isSubmitting} className="mt-6 min-h-[48px] w-full rounded-lg bg-brand font-semibold text-white disabled:opacity-60">
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </button>
        <Link to="/register" className="mt-3 block min-h-[44px] rounded-lg border border-brand py-3 text-center font-semibold text-brand">New staff? Request access</Link>
        <p className="mt-4 text-xs text-slate-500">This system is a screening aid. It does not replace clinical judgement.</p>
      </form>
    </div>
  );
}
