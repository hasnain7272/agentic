import { useState } from 'react';
import { DashboardHeader } from '@/layouts/DashboardHeader';
import { ChatPane } from '@/features/chat/ChatPane';
import { InlineSettingsTab } from '@/features/settings/InlineSettingsTab';
import { MCPPanel } from '@/features/mcp/MCPPanel';

export function DashboardLayout() {
  const [activeTab, setActiveTab] = useState('chat');

  return (
    <div className="flex h-screen w-full flex-col bg-[#0c0c0c] font-sans">
      <DashboardHeader activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1 min-h-0 overflow-hidden bg-[#0c0c0c] relative">
        <div className={`h-full w-full ${activeTab === 'chat' ? '' : 'hidden'}`}>
          <ChatPane />
        </div>
        <div className={`h-full w-full overflow-y-auto custom-scrollbar ${activeTab === 'settings' ? '' : 'hidden'}`}>
          <InlineSettingsTab />
        </div>
        <div className={`h-full w-full ${activeTab === 'mcp' ? '' : 'hidden'}`}>
          <MCPPanel />
        </div>
      </main>
    </div>
  );
}