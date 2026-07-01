import { Check, Loader2, X, Zap } from 'lucide-react';

interface HeaderProps { onClose: () => void; }
interface FooterProps {
  saving: boolean;
  saved: boolean;
  onClose: () => void;
  onSave: () => void;
}

export function ProviderSettingsHeader({ onClose }: HeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/20 to-violet-500/20 ring-1 ring-cyan-500/30">
          <Zap className="h-4 w-4 text-cyan-400" />
        </div>
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Project Settings</h2>
          <p className="text-[11px] text-slate-500">Configure intelligence and resources</p>
        </div>
      </div>
      <button onClick={onClose} className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-800 hover:text-slate-300">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function ProviderSettingsFooter({ saving, saved, onClose, onSave }: FooterProps) {
  return (
    <div className="flex flex-col gap-3 border-t border-slate-800 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-[10px] italic text-slate-600">BYOK: keys stay backend-managed and session-isolated.</p>
      <div className="flex justify-end gap-2">
        <button onClick={onClose} className="rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-1.5 text-xs font-medium text-slate-400 transition hover:bg-slate-700 hover:text-slate-200">
          Cancel
        </button>
        <button onClick={onSave} disabled={saving} className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-cyan-600 to-blue-600 px-4 py-1.5 text-xs font-semibold text-white shadow-lg shadow-cyan-900/40 transition hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50">
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : saved ? <Check className="h-3.5 w-3.5" /> : null}
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Apply Settings'}
        </button>
      </div>
    </div>
  );
}
