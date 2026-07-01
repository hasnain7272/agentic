/**
 * DashboardLayout — SaaS-grade Agentic IDE Layout
 */
import { useState } from 'react';
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels';
import { DashboardHeader } from '@/layouts/DashboardHeader';
import { ChatPane } from '@/features/chat/ChatPane';
import { ProviderSettingsModal } from '@/components/ProviderSettingsModal';
import { SessionDrawer } from '@/components/SessionDrawer';
import { SessionSidebar } from '@/components/SessionSidebar';
import { FileExplorer } from '@/features/workspace/FileExplorer';
import { ConsoleWindow } from '@/features/terminal/ConsoleWindow';
import { WorkspaceManager } from '@/components/WorkspaceManager';
import { CapabilityStudio } from '@/features/capabilities/CapabilityStudio';
import { CapabilitySidebarPanel } from '@/features/capabilities/CapabilityStudio/SidebarPanel';
import { DashboardMobile, type MobileTab } from '@/layouts/DashboardMobile';
import { Files, Zap, Shield, Layout, MessageSquare } from 'lucide-react';

export function DashboardLayout() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [sidebarTab, setSidebarTab] = useState<'sessions'|'files'|'capabilities'>('sessions');
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false);
  const [showCapabilityStudio, setShowCapabilityStudio] = useState(false);
  const [settingsTargetSession, setSettingsTargetSession] = useState<string | undefined>();
  const [mobileTab, setMobileTab] = useState<MobileTab>('agent');

  const handleOpenSettings = (targetId?: string) => {
    setSettingsTargetSession(targetId);
    setSettingsOpen(true);
    setDrawerOpen(false);
  };

  const openCapabilityStudio = () => setShowCapabilityStudio(true);

  return (
    <div className="flex h-screen w-full flex-col bg-slate-950 overflow-hidden font-sans selection:bg-cyan-500/30">
      <DashboardHeader
        onOpenDrawer={() => setDrawerOpen(true)}
        onOpenWorkspaceModal={() => setShowWorkspaceModal(true)}
        showFileExplorer={showSidebar}
        onToggleFileExplorer={() => setShowSidebar(!showSidebar)}
        onOpenCapabilityStudio={openCapabilityStudio}
        onOpenSettings={() => handleOpenSettings()}
      />

      <SessionDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onOpenSettings={handleOpenSettings} />
      <ProviderSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} targetSessionId={settingsTargetSession} />

      <DashboardMobile activeTab={mobileTab} onTabChange={setMobileTab} onOpenStudio={openCapabilityStudio} />

      <main className="hidden flex-1 overflow-hidden bg-slate-950 md:flex">
        <PanelGroup direction="horizontal" autoSaveId="dashboard-layout">
          {showSidebar && (
            <>
              <Panel defaultSize={22} minSize={18} maxSize={45} className="bg-[#0b1120] border-r border-slate-800 flex">
                {/* Slim Sidebar Navigation */}
                <div className="w-12 border-r border-slate-800 flex flex-col items-center py-4 gap-4 bg-slate-900/30">
                  <button onClick={() => setSidebarTab('sessions')}
                    title="Chat Sessions"
                    className={`p-2 rounded-xl transition-all ${sidebarTab === 'sessions' ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-500 hover:text-slate-300'}`}>
                    <MessageSquare className="h-5 w-5" />
                  </button>
                  <button onClick={() => setSidebarTab('files')} 
                    title="Files & Repos"
                    className={`p-2 rounded-xl transition-all ${sidebarTab === 'files' ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-500 hover:text-slate-300'}`}>
                    <Files className="h-5 w-5" />
                  </button>
                  <button onClick={() => setSidebarTab('capabilities')}
                    title="Intelligence Studio"
                    className={`p-2 rounded-xl transition-all ${sidebarTab === 'capabilities' ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-500 hover:text-slate-300'}`}>
                    <Zap className="h-5 w-5" />
                  </button>
                  <div className="mt-auto flex flex-col gap-4 mb-2">
                    <button onClick={() => handleOpenSettings()} className="p-2 text-slate-600 hover:text-slate-300 transition-colors">
                       <Shield className="h-5 w-5" />
                     </button>
                  </div>
                </div>

                {/* Sidebar Content */}
                <div className="flex-1 flex flex-col min-w-0">
                  <div className="h-10 px-4 flex items-center border-b border-slate-800/60 bg-slate-900/10">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      {sidebarTab === 'sessions' ? 'Active Sessions' : sidebarTab === 'files' ? 'Project Workspace' : 'Intelligence Studio'}
                    </span>
                  </div>
                  <div className="flex-1 overflow-hidden">
                    {sidebarTab === 'sessions' && <SessionSidebar onOpenSettings={handleOpenSettings} />}
                    {sidebarTab === 'files' && <FileExplorer />}
                    {sidebarTab === 'capabilities' && <CapabilitySidebarPanel onOpenStudio={openCapabilityStudio} />}
                  </div>
                </div>
              </Panel>
              <PanelResizeHandle className="w-[1.5px] bg-slate-800/80 hover:bg-cyan-500/50 transition-colors cursor-col-resize z-10" />
            </>
          )}

          <Panel defaultSize={48} minSize={30} className="flex flex-col bg-[#020617] border-r border-slate-800 relative shadow-inner">
            <div className="h-10 border-b border-slate-800/60 flex items-center px-4 bg-[#0b1120]/50 justify-between">
              <div className="flex items-center gap-2">
                <Layout className="h-3 w-3 text-slate-500" />
                <div className="flex items-center text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                  <span>System Console</span>
                  <span className="mx-1.5 text-slate-600">/</span>
                  <span className="text-cyan-500/70">Workspace</span>
                </div>
              </div>
            </div>
            <div className="flex-1 overflow-hidden relative">
              <ConsoleWindow />
            </div>
          </Panel>

          <PanelResizeHandle className="w-[1.5px] bg-slate-800/80 hover:bg-cyan-500/50 transition-colors cursor-col-resize z-10 shadow-md" />

          <Panel defaultSize={30} minSize={25} className="flex flex-col bg-[#0b1120]/40 backdrop-blur-sm">
            <ChatPane />
          </Panel>
        </PanelGroup>
      </main>

      <WorkspaceManager externalOpen={showWorkspaceModal} onExternalClose={() => setShowWorkspaceModal(false)} />
      <CapabilityStudio open={showCapabilityStudio} onClose={() => setShowCapabilityStudio(false)} />
    </div>
  );
}
