import { useState } from 'react';
import { DashboardHeader } from '@/layouts/DashboardHeader';
import { ChatPane } from '@/features/chat/ChatPane';
import { SwarmTopology } from '@/features/swarm/SwarmTopology';
import { InlineSettingsTab } from '@/features/settings/InlineSettingsTab';
import { MCPPanel } from '@/features/mcp/MCPPanel';

export function DashboardLayout() {
  const [activeTab, setActiveTab] = useState('chat');

  return (
    <div className="flex h-screen w-full flex-col bg-[#0c0c0c] font-sans">
      <DashboardHeader activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1 min-h-0 overflow-hidden bg-[#0c0c0c]">
        {activeTab === 'chat' && <ChatPane />}
        {activeTab === 'settings' && (
          <div className="h-full w-full overflow-y-auto custom-scrollbar">
            <InlineSettingsTab />
          </div>
        )}
        {activeTab === 'swarm' && <SwarmTopology />}
        {activeTab === 'mcp' && <MCPPanel />}
      </main>
    </div>
  );
}