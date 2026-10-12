import { useEffect, useRef } from 'react';

export default function Modal({ title, onClose, children }) {
  const ref = useRef(null);
  const previous = useRef(document.activeElement);
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    ref.current?.focus();
    const opener = previous.current;
    return () => {
      document.removeEventListener('keydown', onKey);
      opener?.focus?.(); // give focus back to the button that opened the dialog
    };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="modal-title"
        onClick={(e) => e.stopPropagation()} className="w-full max-w-md rounded-xl bg-white p-6">
        <h2 id="modal-title" className="mb-4 text-lg font-bold">{title}</h2>
        {children}
      </div>
    </div>
  );
}
