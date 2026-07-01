import { Bot, Files, TerminalSquare, Zap } from 'lucide-react';
import { ChatPane } from '@/features/chat/ChatPane';
import { FileExplorer } from '@/features/workspace/FileExplorer';
import { ConsoleWindow } from '@/features/terminal/ConsoleWindow';
import { CapabilitySidebarPanel } from '@/features/capabilities/CapabilityStudio/SidebarPanel';

type MobileTab = 'agent' | 'files' | 'console' | 'capabilities';

interface DashboardMobileProps {
  activeTab: MobileTab;
  onTabChange: (tab: MobileTab) => void;
  onOpenStudio: () => void;
}

const TABS = [
  { id: 'agent', label: 'Agent', icon: Bot },
  { id: 'files', label: 'Files', icon: Files },
  { id: 'console', label: 'Console', icon: TerminalSquare },
  { id: 'capabilities', label: 'Tools', icon: Zap },
] as const;

export function DashboardMobile({ activeTab, onTabChange, onOpenStudio }: DashboardMobileProps) {
  return (
    <main className="flex min-h-0 flex-1 flex-col bg-slate-950 md:hidden">
      <nav className="grid grid-cols-4 gap-1 border-b border-slate-800/70 bg-slate-900/70 p-2">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onTabChange(id)}
            className={`flex min-h-11 flex-col items-center justify-center gap-1 rounded-2xl text-[10px] font-bold uppercase tracking-wider transition ${
              activeTab === id
                ? 'bg-cyan-500/15 text-cyan-200 ring-1 ring-cyan-400/25'
                : 'text-slate-500 hover:bg-slate-800/70 hover:text-slate-300'
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </nav>

      <section className="min-h-0 flex-1 overflow-hidden">
        {activeTab === 'agent' && <ChatPane />}
        {activeTab === 'files' && <FileExplorer />}
        {activeTab === 'console' && <ConsoleWindow />}
        {activeTab === 'capabilities' && (
          <CapabilitySidebarPanel onOpenStudio={onOpenStudio} />
        )}
      </section>
    </main>
  );
}

export type { MobileTab };
