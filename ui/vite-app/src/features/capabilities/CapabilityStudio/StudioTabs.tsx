import { Activity, Plug, Search, Sparkles, Terminal, Wrench } from 'lucide-react';

export const tabs = [
  { id: 'skills', label: 'Skills', icon: Sparkles },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'plugins', label: 'HTTP Plugins', icon: Plug },
  { id: 'stdio', label: 'Stdio MCP', icon: Terminal },
  { id: 'dashboard', label: 'Dashboard', icon: Activity },
] as const;

export type StudioTab = (typeof tabs)[number]['id'];

interface Props {
  tab: StudioTab;
  query: string;
  onTab: (tab: StudioTab) => void;
  onQuery: (query: string) => void;
}

export function StudioTabs({ tab, query, onTab, onQuery }: Props) {
  return (
    <div className="flex items-center gap-3 border-b border-slate-800 px-6 py-3">
      <div className="flex flex-wrap gap-2">
        {tabs.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.id} onClick={() => onTab(item.id)} className={`flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold transition ${tab === item.id ? 'bg-slate-800 text-slate-100 ring-1 ring-slate-700' : 'text-slate-500 hover:bg-slate-900 hover:text-slate-300'}`}>
              <Icon className="h-3.5 w-3.5" />{item.label}
            </button>
          );
        })}
      </div>
      <div className="relative ml-auto w-full max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
        <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder={`Search ${tab}...`} className="w-full rounded-xl border border-slate-800 bg-slate-900 px-9 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-600/40" />
      </div>
    </div>
  );
}
