import React, { useEffect, useState } from 'react';
import { Server, Plug, Terminal, ChevronDown, ChevronRight, Play, X, AlertCircle, Plus, RefreshCw } from 'lucide-react';
import { apiClient } from '@/api/client';
import { useServerEventStream } from '@/store/useServerEventStream';

export function CapabilitySidebarPanel({ onOpenStudio }: { onOpenStudio: () => void }) {
  const [stdioServers, setStdioServers] = useState<any[]>([]);
  const [plugins, setPlugins] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [tools, setTools] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(false);
  const { lastEvent } = useServerEventStream();

  const reload = async () => {
    setLoading(true);
    const [stdioRes, catRes] = await Promise.all([
      apiClient.get<any>('/mcp/stdio/servers'),
      apiClient.get<any>('/mcp/catalog'),
    ]);
    setStdioServers(stdioRes.data?.servers || []);
    setPlugins(catRes.data?.plugins || []);
    setLoading(false);
  };

  useEffect(() => { reload(); }, []);
  useEffect(() => {
    if (!lastEvent) return;
    if (['CATALOG_UPDATED', 'DASHBOARD_UPDATED', 'STDIO_UPDATED', 'STDIO_SERVERS_UPDATED', 'PLUGINS_UPDATED'].includes(lastEvent.type)) {
      reload();
    }
  }, [lastEvent]);

  const toggleServer = async (name: string) => {
    if (expanded === name) { setExpanded(null); return; }
    setExpanded(name);
    if (!tools[name]) {
      const res = await apiClient.get<any>(`/mcp/stdio/${name}/tools`);
      setTools(prev => ({ ...prev, [name]: res.data?.tools || [] }));
    }
  };

  const statusColor = (s: string) =>
    s === 'running' ? 'bg-emerald-500' : s === 'error' ? 'bg-red-500' : 'bg-amber-500';

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Stdio MCP Servers */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Terminal className="h-3.5 w-3.5 text-violet-400" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Stdio Servers</span>
            </div>
            <button onClick={reload} className="p-1 text-slate-500 hover:text-slate-300 transition" title="Refresh">
              <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          {loading ? (
            <div className="space-y-1.5 mb-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-9 rounded-lg bg-slate-800/60 animate-pulse border border-slate-800" />
              ))}
            </div>
          ) : stdioServers.length === 0 ? (
            <div className="text-[10px] text-slate-600 px-1 py-2 italic">No stdio servers yet.</div>
          ) : null}
          {stdioServers.map(s => (
            <div key={s.name} className="mb-1.5 rounded-lg border border-slate-800 bg-slate-900/40 overflow-hidden">
              <button onClick={() => toggleServer(s.name)}
                className="w-full flex items-center gap-2 px-2.5 py-2 text-left hover:bg-slate-800/50 transition">
                {expanded === s.name ? <ChevronDown className="h-3 w-3 text-slate-500" /> : <ChevronRight className="h-3 w-3 text-slate-500" />}
                <div className={`w-1.5 h-1.5 rounded-full ${statusColor(s.status)}`} />
                <span className="text-[11px] font-semibold text-slate-200 truncate">{s.name}</span>
                <span className="ml-auto text-[9px] text-slate-600">{s.tool_count} tools</span>
              </button>
              {expanded === s.name && tools[s.name] && (
                <div className="border-t border-slate-800 px-2.5 py-2 space-y-1 bg-slate-950/40">
                  {tools[s.name].map((t: any) => (
                    <div key={t.name} className="flex items-center justify-between py-1">
                      <span className="text-[10px] text-slate-300 truncate mr-2">{t.name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* HTTP Plugins */}
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Plug className="h-3.5 w-3.5 text-emerald-400" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">HTTP Plugins</span>
          </div>
          {loading ? (
            <div className="space-y-1.5">
              {[...Array(2)].map((_, i) => (
                <div key={i} className="h-8 rounded-lg bg-slate-800/60 animate-pulse border border-slate-800" />
              ))}
            </div>
          ) : plugins.length === 0 ? (
            <div className="text-[10px] text-slate-600 px-1 py-2 italic">No plugins registered.</div>
          ) : (
            plugins.map((p: any) => (
              <div key={p.name} className="flex items-center gap-2 px-2.5 py-2 mb-1 rounded-lg border border-slate-800 bg-slate-900/40">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span className="text-[11px] font-semibold text-slate-200 truncate">{p.name}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Open Full Studio CTA */}
      <div className="p-3 border-t border-slate-800/60">
        <button onClick={onOpenStudio}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-600 to-violet-600 px-3 py-2.5 text-[11px] font-bold text-white shadow-lg shadow-cyan-900/20 hover:shadow-cyan-900/40 transition-all hover:scale-[1.02] active:scale-[0.98]">
          <Server className="h-3.5 w-3.5" />
          Open Capability Studio
        </button>
      </div>
    </div>
  );
}
