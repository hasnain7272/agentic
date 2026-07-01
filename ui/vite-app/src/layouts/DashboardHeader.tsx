import { useState, useEffect } from 'react';
import { Layers, Settings, LogOut } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { useSessionStore } from '@/store/sessionStore';
import { apiClient } from '@/api/client';

interface DashboardHeaderProps {
  onOpenDrawer: () => void;
  onOpenSettings: () => void;
}

export function DashboardHeader({
  onOpenDrawer,
  onOpenSettings
}: DashboardHeaderProps) {
  const [tenantInfo, setTenantInfo] = useState<any>(null);
  const userEmail = useSessionStore((s) => s.userEmail);
  const spendUsd = (tenantInfo?.cost_cents || 0) / 100;
  const quotaUsd = tenantInfo?.quota_usd || 0;
  const spendPercent = quotaUsd > 0 ? Math.min(100, (spendUsd / quotaUsd) * 100) : 0;

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

  return (
    <header className="flex min-h-14 shrink-0 items-center justify-between gap-2 border-b border-slate-800 bg-slate-950 px-2 py-2 md:h-12 md:px-4 md:py-0">
      <div className="flex min-w-0 flex-1 items-center gap-2 md:gap-3">
        <button
          onClick={onOpenDrawer}
          className="group flex shrink-0 items-center gap-2 rounded-lg px-2 py-1.5 transition hover:bg-slate-900 active:scale-95 md:gap-2.5 md:px-2.5"
        >
          <div className="flex h-6 w-6 items-center justify-center rounded bg-emerald-500">
            <Layers className="h-3.5 w-3.5 text-white transition group-hover:scale-110" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-slate-100">Antigravity</span>
        </button>
        
        <Badge variant="outline" className="hidden h-4 border-slate-700 bg-slate-900 px-1.5 font-mono text-[9px] text-slate-400 sm:inline-flex">v4.0.0</Badge>
      </div>

      <div className="flex shrink-0 items-center gap-1.5 md:gap-3">
        {tenantInfo && (
          <div className="hidden w-32 flex-col gap-1 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 lg:flex" title="API Budget">
            <div className="flex justify-between items-center text-[9px] font-bold tracking-wider uppercase text-slate-400">
              <span>Spend</span>
              <span className={`${spendPercent >= 90 ? 'text-red-400' : 'text-slate-300'}`}>
                ${spendUsd.toFixed(2)} / ${quotaUsd}
              </span>
            </div>
            <div className="h-1.5 w-full bg-slate-900 rounded-full overflow-hidden">
              <div 
                className={`h-full ${spendPercent >= 90 ? 'bg-red-500' : 'bg-emerald-500'} transition-all`} 
                style={{ width: `${spendPercent}%` }} 
              />
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 p-1.5 md:px-3">
          <div className="w-5 h-5 rounded-full bg-slate-700 flex items-center justify-center text-[10px] font-bold text-white">
            {userEmail?.[0]?.toUpperCase() || 'U'}
          </div>
          <span className="hidden max-w-32 truncate text-[11px] font-medium tracking-tight text-slate-300 md:block">
            {userEmail || 'User'}
          </span>
          <div className="mx-0.5 hidden h-4 w-[1px] bg-slate-800/40 md:block" />
          <button onClick={handleLogout} className="text-slate-500 transition-colors hover:text-red-400 md:text-[10px] md:font-bold md:uppercase">
            <LogOut className="h-3.5 w-3.5 md:hidden" />
            <span className="hidden md:inline">Logout</span>
          </button>
        </div>
        
        <button
          onClick={onOpenSettings}
          className="group flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-slate-400 transition-all hover:bg-slate-900 hover:text-slate-200"
        >
          <Settings className="h-3.5 w-3.5 text-slate-500 transition group-hover:rotate-45" />
        </button>
      </div>
    </header>
  );
}
