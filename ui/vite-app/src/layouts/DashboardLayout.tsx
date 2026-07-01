import { useState } from 'react';
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels';
import { DashboardHeader } from '@/layouts/DashboardHeader';
import { ChatPane } from '@/features/chat/ChatPane';
import { ProviderSettingsModal } from '@/components/ProviderSettingsModal';
import { SessionDrawer } from '@/components/SessionDrawer';
import { SessionSidebar } from '@/components/SessionSidebar';
import { DashboardMobile } from '@/layouts/DashboardMobile';

export function DashboardLayout() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [settingsTargetSession, setSettingsTargetSession] = useState<string | undefined>();

  const handleOpenSettings = (targetId?: string) => {
    setSettingsTargetSession(targetId);
    setSettingsOpen(true);
    setDrawerOpen(false);
  };

  return (
    <div className="flex h-screen w-full flex-col bg-slate-950 overflow-hidden font-sans selection:bg-emerald-500/30">
      <DashboardHeader
        onOpenDrawer={() => setDrawerOpen(true)}
        onOpenSettings={() => handleOpenSettings()}
      />

      <SessionDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onOpenSettings={handleOpenSettings} />
      <ProviderSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} targetSessionId={settingsTargetSession} />

      <DashboardMobile />

      <main className="hidden flex-1 overflow-hidden bg-slate-950 md:flex">
        <PanelGroup direction="horizontal" autoSaveId="dashboard-layout">
          {showSidebar && (
            <>
              <Panel defaultSize={22} minSize={18} maxSize={35} className="bg-slate-950 border-r border-slate-800 flex flex-col">
                <div className="h-10 px-4 flex items-center border-b border-slate-800 bg-slate-950">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                    Active Sessions
                  </span>
                </div>
                <div className="flex-1 overflow-hidden">
                  <SessionSidebar onOpenSettings={handleOpenSettings} />
                </div>
              </Panel>
              <PanelResizeHandle className="w-[1.5px] bg-slate-800 hover:bg-emerald-500/60 transition-colors cursor-col-resize z-10" />
            </>
          )}

          <Panel defaultSize={78} minSize={50} className="flex flex-col bg-slate-950">
            <ChatPane />
          </Panel>
        </PanelGroup>
      </main>
    </div>
  );
}
