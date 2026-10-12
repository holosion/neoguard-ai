import { RISK_CATEGORIES } from '../../utils/constants';

export default function RiskBadge({ category }) {
  const c = RISK_CATEGORIES[category] ?? RISK_CATEGORIES.no_data;
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${c.bg} ${c.text}`}>{c.label}</span>;
}
