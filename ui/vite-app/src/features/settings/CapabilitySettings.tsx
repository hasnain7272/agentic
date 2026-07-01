import { Server } from 'lucide-react';
import { StdioTab } from '@/features/capabilities/CapabilityStudio/StdioTab';
import { HttpPluginSettings } from '@/features/settings/HttpPluginSettings';

export function CapabilitySettings() {
  return (
    <div className="space-y-6 p-6 pt-2">
      <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-slate-500/80">
        <Server className="h-3 w-3" />
        Capabilities
      </label>
      <StdioTab onServersChanged={() => window.dispatchEvent(new Event('ag-capabilities-changed'))} />
      <HttpPluginSettings />
    </div>
  );
}
