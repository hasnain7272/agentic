import { useEffect, useMemo, useState } from 'react';
import { DashboardTab } from './DashboardTab';
import { PluginsTab } from './PluginsTab';
import { SkillsTab } from './SkillsTab';
import { StdioTab } from './StdioTab';
import { StudioHeader } from './StudioHeader';
import { StudioTabs, type StudioTab } from './StudioTabs';
import { SummaryStrip } from './SummaryStrip';
import { ToolsTab } from './ToolsTab';
import { useCapabilityStudio } from './useCapabilityStudio';

type Props = { open: boolean; onClose: () => void };

export function CapabilityStudio({ open, onClose }: Props) {
  const [tab, setTab] = useState<StudioTab>('skills');
  const [query, setQuery] = useState('');
  const studio = useCapabilityStudio();
  const text = query.toLowerCase();
  const catalog = studio.catalog;

  useEffect(() => {
    if (!open) return;
    studio.refresh(tab === 'dashboard');
  }, [open, tab, studio.refresh]);

  const filtered = useMemo(() => ({
    skills: (catalog?.skills || []).filter((item) => `${item.name} ${item.description} ${item.missing_tools?.join(' ')}`.toLowerCase().includes(text)),
    tools: (catalog?.tools || []).filter((item) => `${item.name} ${item.description} ${item.category}`.toLowerCase().includes(text)),
    plugins: (catalog?.plugins || []).filter((item) => `${item.name} ${item.description}`.toLowerCase().includes(text)),
  }), [catalog, text]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="flex h-[85vh] w-full max-w-6xl flex-col overflow-hidden rounded-3xl border border-slate-800 bg-slate-950 shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <StudioHeader onClose={onClose} />
        <SummaryStrip counts={studio.counts} onRefresh={() => studio.refresh(tab === 'dashboard')} />
        <StudioTabs tab={tab} query={query} onTab={setTab} onQuery={setQuery} />
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {studio.loading && <div className="text-sm text-slate-500">Loading capabilities...</div>}
          {studio.error && <div className="rounded-xl border border-red-900/50 bg-red-950/20 px-3 py-2 text-sm text-red-300">{studio.error}</div>}
          {!studio.loading && !studio.error && tab === 'skills' && <SkillsTab skills={filtered.skills} onClose={onClose} />}
          {!studio.loading && !studio.error && tab === 'tools' && <ToolsTab tools={filtered.tools} categories={catalog?.categories || []} />}
          {!studio.loading && !studio.error && tab === 'plugins' && <PluginsTab plugins={filtered.plugins} onPluginsChanged={() => studio.refresh(true)} />}
          {!studio.loading && !studio.error && tab === 'stdio' && <StdioTab onServersChanged={() => studio.refresh(false)} />}
          {!studio.loading && !studio.error && tab === 'dashboard' && <DashboardTab dashboard={studio.dashboard} onDashboardChanged={() => studio.refresh(true)} />}
        </div>
      </div>
    </div>
  );
}
