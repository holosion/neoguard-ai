export default function Skeleton({ rows = 5 }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-12 animate-pulse motion-reduce:animate-none rounded-lg bg-slate-200" />
      ))}
    </div>
  );
}
