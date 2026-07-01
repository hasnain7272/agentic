import { AlertTriangle, Boxes, Plug, Sparkles, Terminal, Wrench } from 'lucide-react';
import type { CapabilitySummary } from './types';

interface Props {
  counts: CapabilitySummary;
  onRefresh: () => void;
}

export function SummaryStrip({ counts, onRefresh }: Props) {
  return (
    <div className="grid gap-2 border-b border-slate-800 bg-slate-950/70 px-6 py-3 md:grid-cols-7">
      <Metric icon={Sparkles} label="Ready Skills" value={`${counts.ready_skills}/${counts.skills}`} tone="text-cyan-300 bg-cyan-500/10" />
      <Metric icon={Wrench} label="Tools" value={counts.tools} tone="text-emerald-300 bg-emerald-500/10" />
      <Metric icon={Plug} label="Plugins" value={counts.plugins} tone="text-violet-300 bg-violet-500/10" />
      <Metric icon={Terminal} label="Stdio" value={`${counts.stdio_running || 0}/${counts.stdio_servers || 0}`} tone="text-fuchsia-300 bg-fuchsia-500/10" />
      <Metric icon={Boxes} label="Categories" value={counts.categories} tone="text-slate-300 bg-slate-800" />
      <Metric icon={AlertTriangle} label="Missing" value={counts.missing_skill_tools} tone={counts.missing_skill_tools ? 'text-amber-300 bg-amber-500/10' : 'text-slate-500 bg-slate-800'} />
      <button onClick={onRefresh} className="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-300 transition hover:border-cyan-700 hover:text-cyan-300">Refresh</button>
    </div>
  );
}

function Metric({ icon: Icon, label, value, tone }: { icon: typeof Boxes; label: string; value: string | number; tone: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
      <span className={`rounded-lg p-1.5 ${tone}`}><Icon className="h-3.5 w-3.5" /></span>
      <div>
        <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
        <div className="text-sm font-semibold text-slate-100">{value}</div>
      </div>
    </div>
  );
}
