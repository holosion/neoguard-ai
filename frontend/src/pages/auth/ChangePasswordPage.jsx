import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAuthStore } from '../../store/authStore';

const schema = z.object({
  old_password: z.string().min(1, 'Enter your current password'),
  new_password: z.string().min(12, 'Use at least 12 characters').max(128),
  confirm_password: z.string().min(1, 'Confirm your new password'),
}).refine((values) => values.new_password === values.confirm_password, {
  path: ['confirm_password'], message: 'Passwords do not match',
});

export default function ChangePasswordPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const mustChangePassword = useAuthStore((state) => state.mustChangePassword);
  const changePassword = useAuthStore((state) => state.changePassword);
  const navigate = useNavigate();
  const [formError, setFormError] = useState(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema) });

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const submit = async ({ old_password, new_password }) => {
    setFormError(null);
    try {
      const user = await changePassword(old_password, new_password);
      navigate(user.role === 'admin' ? '/admin' : '/', { replace: true });
    } catch (error) {
      const detail = error.response?.data?.detail;
      setFormError(typeof detail === 'string' ? detail : 'Could not change your password. Check your connection and try again.');
    }
  };

  const field = 'mt-1 min-h-[44px] w-full rounded-lg border border-slate-400 px-3 text-base';
  const error = (name) => errors[name] && <p className="mt-1 text-sm text-red-700">{errors[name].message}</p>;
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={handleSubmit(submit)} noValidate className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8">
        <h1 className="text-xl font-bold text-brand">{mustChangePassword ? 'Set your password' : 'Change password'}</h1>
        <p className="mb-5 mt-2 text-sm text-slate-600">{mustChangePassword ? 'Your temporary password is only valid for 24 hours. Choose a new password to continue.' : 'Use at least 12 characters.'}</p>
        <label className="block text-sm">Current password<input type="password" autoComplete="current-password" className={field} {...register('old_password')} /></label>{error('old_password')}
        <label className="mt-4 block text-sm">New password<input type="password" autoComplete="new-password" className={field} {...register('new_password')} /></label>{error('new_password')}
        <label className="mt-4 block text-sm">Confirm new password<input type="password" autoComplete="new-password" className={field} {...register('confirm_password')} /></label>{error('confirm_password')}
        {formError && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{formError}</p>}
        <button disabled={isSubmitting} className="mt-6 min-h-[48px] w-full rounded-lg bg-brand font-semibold text-white disabled:opacity-60">{isSubmitting ? 'Saving…' : 'Save new password'}</button>
      </form>
    </div>
  );
}
