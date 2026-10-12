export const RISK_CATEGORIES = {
  critical: { label: 'Critical', bg: 'bg-red-100', text: 'text-red-800', rank: 0 },
  high: { label: 'High', bg: 'bg-orange-100', text: 'text-orange-800', rank: 1 },
  medium: { label: 'Medium', bg: 'bg-yellow-100', text: 'text-yellow-800', rank: 2 },
  low: { label: 'Low', bg: 'bg-green-100', text: 'text-green-800', rank: 3 },
  no_data: { label: 'No data', bg: 'bg-slate-100', text: 'text-slate-600', rank: 4 },
};

export const DEVICE_STATUS = {
  online: { label: 'Online' },
  stale: { label: 'Stale' },
  offline: { label: 'Offline' },
};

// A reading older than this is shown as stale (muted, with a banner).
export const STALE_AFTER_MINUTES = 10;
export const POLL_INTERVAL_MS = 30000;

export const PARAMETER_LABELS = { hr: 'Heart rate', spo2: 'SpO₂', temp: 'Temperature', ai: 'AI trend', quality: 'Sensor quality' };

// Roles that may register patients and start or end sessions. The backend currently allows admin and clinician only.
// If nurses are allowed later, add 'nurse' here and the buttons appear for them.
export const SESSION_MANAGER_ROLES = ['admin', 'clinician'];
