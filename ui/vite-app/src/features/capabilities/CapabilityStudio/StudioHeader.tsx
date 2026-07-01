import { Boxes, X } from 'lucide-react';

export function StudioHeader({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-400 ring-1 ring-cyan-500/20">
          <Boxes className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-100">Capability Studio</h2>
          <p className="text-xs text-slate-500">Skills, tools, plugins, and MCP servers</p>
        </div>
      </div>
      <button onClick={onClose} className="rounded-xl p-2 text-slate-500 transition hover:bg-slate-800 hover:text-slate-200">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
