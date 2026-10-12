export default function EmptyState({ message, action }) {
  return (
    <div className="py-12 text-center">
      <p className="text-slate-500">{message}</p>
      {action && (
        <button onClick={action.onClick} className="mt-4 rounded-lg bg-brand px-4 py-2 font-semibold text-white">
          {action.label}
        </button>
      )}
    </div>
  );
}
