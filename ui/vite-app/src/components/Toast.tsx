/**
 * Toast Notification System — Global notification layer
 * Zustand store + rendered component for success/error/info toasts.
 */
import { create } from 'zustand';
import { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react';

/* ── Store ─────────────────────────────────────────────── */
interface Toast {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
  duration?: number;
}

interface ToastState {
  toasts: Toast[];
  addToast: (type: Toast['type'], message: string, duration?: number) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (type, message, duration = 4000) => {
    const id = `toast_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    set((s) => ({ toasts: [...s.toasts, { id, type, message, duration }] }));
    if (duration > 0) {
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
      }, duration);
    }
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

/* ── Icons & Styles ────────────────────────────────────── */
const ICON_MAP = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

const STYLE_MAP = {
  success: 'border-emerald-500/30 bg-emerald-950/80 text-emerald-300',
  error: 'border-red-500/30 bg-red-950/80 text-red-300',
  info: 'border-cyan-500/30 bg-cyan-950/80 text-cyan-300',
};

const ICON_COLOR = {
  success: 'text-emerald-400',
  error: 'text-red-400',
  info: 'text-cyan-400',
};

/* ── Rendered Component ────────────────────────────────── */
export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => {
        const Icon = ICON_MAP[t.type];
        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-center gap-2.5 rounded-xl border px-4 py-3 shadow-2xl shadow-black/40 backdrop-blur-md animate-in slide-in-from-right-5 fade-in duration-300 ${STYLE_MAP[t.type]}`}
          >
            <Icon className={`h-4 w-4 shrink-0 ${ICON_COLOR[t.type]}`} />
            <span className="text-xs font-medium">{t.message}</span>
            <button
              onClick={() => removeToast(t.id)}
              className="ml-2 shrink-0 rounded p-0.5 opacity-60 transition hover:opacity-100"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
