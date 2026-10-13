import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

const schema = z.object({
  username: z.string().min(1, 'Enter your username'),
  password: z.string().min(1, 'Enter your password'),
});

export default function LoginPage() {
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [formError, setFormError] = useState(null);
  const [showExpiredNotice, setShowExpiredNotice] = useState(false);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!params.has('expired')) return;
    setShowExpiredNotice(true);
    const nextParams = new URLSearchParams(params);
    nextParams.delete('expired');
    setParams(nextParams, { replace: true });
  }, [params, setParams]);

  useEffect(() => {
    if (!showExpiredNotice) return undefined;
    const timeout = window.setTimeout(() => setShowExpiredNotice(false), 5000);
    return () => window.clearTimeout(timeout);
  }, [showExpiredNotice]);

  const onSubmit = async ({ username, password }) => {
    setFormError(null);
    try {
      const user = await login(username, password);
      if (user.must_change_password) {
        navigate('/change-password', { replace: true });
        return;
      }
      navigate(user.role === 'admin' ? '/admin' : '/', { replace: true });
    } catch (e) {
      if (e.response?.status === 429) {
        setFormError('Too many sign-in attempts. Wait 15 minutes and try again.');
        return;
      }
      if (e.response?.status === 403 && typeof e.response?.data?.detail === 'string') {
        setFormError(e.response.data.detail);
        return;
      }
      setFormError('Sign in failed. Check your username and password, or ask an administrator if your account is approved.');
    }
  };

  const field = 'login-field mt-2 min-h-[48px] w-full rounded-lg px-3 text-base';
  return (
    <main className="login-page">
      <section className="login-card" aria-label="NeoGuard staff sign in">
        <div className="login-banner" aria-hidden="true">
          <div className="login-banner-content">
            <div className="login-brand-mark"><span className="login-brand-dot" /> NEOGUARD</div>
            <p className="login-eyebrow">NEONATAL MONITORING</p>
            <h1>Welcome<br />back.</h1>
            <p className="login-banner-copy">Sign in to your workspace to continue monitoring care.</p>
            <div className="login-signal" aria-hidden="true">
              <span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span />
            </div>
          </div>
          <span className="login-orb login-orb-one" />
          <span className="login-orb login-orb-two" />
          <span className="login-orb login-orb-three" />
        </div>

        <div className="login-form-wrap">
          <form onSubmit={handleSubmit(onSubmit)} className="login-form" noValidate>
            <div className="login-form-heading">
              <p className="login-eyebrow">STAFF PORTAL</p>
              <h2>Sign in</h2>
              <p>Enter your account details to continue.</p>
            </div>
            {showExpiredNotice && <p role="status" className="login-notice">Your sign-in expired. Sign in again to continue.</p>}
            <label className="login-label">Username
              <input className={field} autoComplete="username" placeholder="Enter your username" {...register('username')} />
            </label>
            {errors.username && <p className="login-field-error">{errors.username.message}</p>}
            <label className="login-label login-password-label">Password
              <input type="password" className={field} autoComplete="current-password" placeholder="Enter your password" {...register('password')} />
            </label>
            {errors.password && <p className="login-field-error">{errors.password.message}</p>}
            {formError && <p role="alert" className="login-error">{formError}</p>}
            <button disabled={isSubmitting} className="login-submit">
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
