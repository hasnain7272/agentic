import { useState, useEffect } from 'react';
import { Settings, LogOut, MessageSquare, Folder, Cpu, Network, Terminal } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { apiClient } from '@/api/client';
import { useSessions } from '@/components/session-drawer/useSessions';

interface DashboardHeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export function DashboardHeader({
  activeTab,
  setActiveTab,
}: DashboardHeaderProps) {
  const [tenantInfo, setTenantInfo] = useState<any>(null);
  const userEmail = useSessionStore((s) => s.userEmail);
  const spendUsd = (tenantInfo?.cost_cents || 0) / 100;
  const quotaUsd = tenantInfo?.quota_usd || 0;
  const spendPercent = quotaUsd > 0 ? Math.min(100, (spendUsd / quotaUsd) * 100) : 0;

  const { sessions, currentSessionId, switchSession, createSession, loadSessions } = useSessions(() => {}, () => {});

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    const fetchMe = async () => {
      try {
        const res = await apiClient.get<any>('/auth/me');
        if (res.data) setTenantInfo(res.data);
      } catch (e) {
        // Ignored
      }
    };
    fetchMe();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    useSessionStore.getState().reset();
    window.location.href = '#/login';
  };

  const tabs = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'workspaces', label: 'Workspaces', icon: Folder },
    { id: 'capabilities', label: 'Capabilities', icon: Cpu },
    { id: 'swarm', label: 'Swarm', icon: Network },
    { id: 'console', label: 'Console', icon: Terminal },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-[#1e1e1e] bg-[#0c0c0c] px-4">
      {/* Session selector */}
      <div className="flex min-w-0 items-center gap-2">
        <span className="text-xs font-bold tracking-tight text-white select-none">
          Agentic OS
        </span>
        <div className="h-4 w-px bg-[#1e1e1e]" />
        <select
          value={currentSessionId || ''}
          onChange={(e) => {
            if (e.target.value === 'new') {
              createSession();
            } else {
              switchSession(e.target.value);
            }
          }}
          className="bg-transparent border-0 font-semibold text-slate-300 hover:text-white outline-none text-[11px] max-w-[140px] truncate cursor-pointer"
        >
          {sessions.map((s) => (
            <option key={s.id} value={s.id} className="bg-[#0c0c0c] text-slate-200">
              {s.name || s.id.slice(0, 8)}
            </option>
          ))}
          <option value="new" className="bg-[#0c0c0c] text-emerald-400 font-bold">+ New Session</option>
        </select>
      </div>

      {/* Tabs navigation */}
      <nav className="flex items-center gap-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex h-8 items-center gap-1.5 rounded-lg px-3 text-[11px] font-semibold transition-all ${
                active
                  ? 'bg-emerald-600/10 text-emerald-400 border border-emerald-500/20'
                  : 'text-slate-400 hover:bg-[#1a1a1a] hover:text-slate-200 border border-transparent'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Right controls */}
      <div className="flex shrink-0 items-center gap-2">
        {tenantInfo && (
          <div className="hidden w-28 flex-col gap-0.5 rounded border border-[#1e1e1e] bg-[#0c0c0c] px-2 py-0.5 text-[9px] lg:flex" title="API Budget">
            <div className="flex justify-between text-slate-500">
              <span>Spend</span>
              <span className={spendPercent >= 90 ? 'text-red-400' : 'text-slate-400'}>
                ${spendUsd.toFixed(2)}
              </span>
            </div>
            <div className="h-1 w-full bg-[#1e1e1e] rounded-full overflow-hidden">
              <div 
                className={spendPercent >= 90 ? 'bg-red-500' : 'bg-emerald-500'} 
                style={{ width: `${spendPercent}%` }} 
              />
            </div>
          </div>
        )}

        <div className="flex items-center gap-1.5 rounded-lg border border-[#1e1e1e] bg-[#0c0c0c] px-2 py-1">
          <div className="w-5 h-5 rounded-full bg-[#1e1e1e] flex items-center justify-center text-[10px] font-bold text-white">
            {userEmail?.[0]?.toUpperCase() || 'U'}
          </div>
          <span className="hidden max-w-24 truncate text-[11px] font-medium text-slate-400 sm:block">
            {userEmail || 'User'}
          </span>
          <div className="mx-1 h-4 w-px bg-[#1e1e1e] hidden sm:block" />
          <button 
            onClick={handleLogout} 
            className="text-slate-500 hover:text-red-400 transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </header>
  );
}