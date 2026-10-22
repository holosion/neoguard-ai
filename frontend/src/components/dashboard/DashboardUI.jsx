import { Activity, AlertTriangle, RadioTower } from 'lucide-react';

export const DASH_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
  stable: '#22c55e',
  neutral: '#94a3b8',
  blue: '#60a5fa',
  purple: '#a78bfa',
  grid: '#263449',
  text: '#a8b6c9',
};

export function DashboardFrame({ children }) {
  return <div className="dashboard-page -m-4 min-h-screen p-4 md:-m-7 md:p-7">{children}</div>;
}

export function DashboardPanel({ title, subtitle, action, children, className = '' }) {
  return (
    <section className={`dashboard-panel ${className}`}>
      <header className="mb-4 flex flex-wrap items-start gap-3">
        <div className="mr-auto">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

const ICONS = { critical: AlertTriangle, high: AlertTriangle, stable: Activity, neutral: RadioTower };

export function MetricCard({ label, value, note, tone = 'blue', icon = 'neutral', onClick, active = false }) {
  const Icon = ICONS[icon] ?? Activity;
  const classes = `metric-card metric-${tone} ${active ? 'metric-selected' : ''} ${onClick ? 'metric-interactive' : ''}`;
  const content = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-[0.12em] text-slate-400">{label}</span>
        <span className="metric-icon"><Icon size={16} aria-hidden="true" /></span>
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-white">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{note}</div>
    </>
  );
  return onClick ? <button type="button" onClick={onClick} aria-pressed={active} className={classes}>{content}</button> : <div className={classes}>{content}</div>;
}

export function DashboardHeading({ title, subtitle, updatedAt, onRefresh, error }) {
  return (
    <div className="mb-6 flex flex-wrap items-end gap-3">
      <div className="mr-auto">
        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-blue-300">NeoGuard · Live monitoring</p>
        <h1 className="text-2xl font-bold tracking-tight text-white md:text-3xl">{title}</h1>
        <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
      </div>
      <div className="text-right text-xs text-slate-400">
        {updatedAt && <span>Updated {updatedAt.toLocaleTimeString()}</span>}
        {error && <span role="status" className="block text-amber-300">Refresh failed · showing last available data</span>}
      </div>
      {onRefresh && <button onClick={onRefresh} className="dashboard-button">Refresh data</button>}
    </div>
  );
}
