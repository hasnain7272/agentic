import { useState } from 'react';
import { DashboardHeader } from '@/layouts/DashboardHeader';
import { ChatPane } from '@/features/chat/ChatPane';
import { WorkspaceManager } from '@/components/WorkspaceManager';
import { CapabilityStudio } from '@/features/capabilities/CapabilityStudio';
import { SwarmTopology } from '@/features/swarm/SwarmTopology';
import { ConsoleWindow } from '@/features/terminal/ConsoleWindow';
import { InlineSettingsTab } from '@/features/settings/InlineSettingsTab';

export function DashboardLayout() {
  const [activeTab, setActiveTab] = useState('chat');

  return (
    <div className="flex h-screen w-full flex-col bg-[#0c0c0c] font-sans">
      <DashboardHeader activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1 min-h-0 overflow-hidden bg-[#0c0c0c]">
        {activeTab === 'chat' && <ChatPane />}
        {activeTab === 'workspaces' && (
          <div className="h-full w-full overflow-y-auto custom-scrollbar p-6">
            <WorkspaceManager />
          </div>
        )}
        {activeTab === 'capabilities' && <CapabilityStudio inline={true} />}
        {activeTab === 'swarm' && <SwarmTopology />}
        {activeTab === 'console' && (
          <div className="h-full w-full overflow-hidden bg-slate-950 p-4">
            <div className="h-full w-full rounded-2xl border border-[#1e1e1e] bg-[#020617] overflow-hidden">
              <ConsoleWindow />
            </div>
          </div>
        )}
        {activeTab === 'settings' && (
          <div className="h-full w-full overflow-y-auto custom-scrollbar">
            <InlineSettingsTab />
          </div>
        )}
      </main>
    </div>
  );
}