import { useEffect, useState } from 'react';
import { useSessionStore } from '@/store/sessionStore';
import { apiClient } from '@/api/client';
import { Cpu, Terminal, Plus, Trash2, Shield, Loader2, Wifi, Activity } from 'lucide-react';
import { useToastStore } from '@/components/Toast';

interface McpServer {
  name: string;
  description?: string;
  type?: string;
  status?: string;
}

export function MCPPanel() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const addToast = useToastStore((s) => s.addToast);

  const [servers, setServers] = useState<McpServer[]>([]);
  const [loading, setLoading] = useState(false);

  // Form state for custom MCP
  const [customName, setCustomName] = useState('');
  const [customCmd, setCustomCmd] = useState('');
  const [customArgs, setCustomArgs] = useState('');
  const [customDesc, setCustomDesc] = useState('');

  const loadMcp = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await apiClient.get<any>(`/mcp/stdio/servers?session_id=${sessionId}`);
      setServers(res.data?.servers || []);
    } catch (e) {
      console.error('Failed to load MCP config', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMcp();
  }, [sessionId]);

  const handleRegisterCustom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionId || !customName || !customCmd) return;
    try {
      const payload = {
        session_id: sessionId,
        name: customName,
        command: customCmd,
        args: customArgs.split(',').map(s => s.trim()).filter(Boolean),
        description: customDesc || undefined,
      };
      await apiClient.post<any>('/mcp/stdio/register', payload);
      addToast('success', `Custom MCP server '${customName}' registered!`);
      setCustomName('');
      setCustomCmd('');
      setCustomArgs('');
      setCustomDesc('');
      loadMcp();
    } catch (err: any) {
      addToast('error', err.message || 'Failed to register custom server');
    }
  };

  const handleDeleteCustom = async (name: string) => {
    if (!sessionId) return;
    try {
      await apiClient.delete(`/mcp/stdio/${name}?session_id=${sessionId}`);
      addToast('success', `Custom MCP '${name}' removed.`);
      loadMcp();
    } catch (err: any) {
      addToast('error', err.message || 'Failed to remove server');
    }
  };

  return (
    <div className="h-full w-full overflow-y-auto custom-scrollbar p-6 bg-[#0c0c0c] text-slate-200">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
          <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-400">
            <Cpu className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Model Context Protocol (MCP)</h2>
            <p className="text-xs text-slate-500">View out-of-the-box pre-built MCP servers or register custom ones.</p>
          </div>
          {loading && <Loader2 className="h-4 w-4 animate-spin text-slate-500 ml-auto" />}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* List Section */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Active MCP Swarm Servers</h3>
            <div className="space-y-2">
              {servers.map((srv) => (
                <div key={srv.name} className="flex items-center justify-between rounded-xl border border-slate-850 bg-[#0f0f11] p-3 text-xs">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white">{srv.name}</span>
                      <span className={`rounded px-1.5 py-0.5 text-[8px] font-bold uppercase ${
                        srv.type === 'builtin'
                          ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/30'
                          : 'bg-cyan-950/40 text-cyan-400 border border-cyan-900/30'
                      }`}>
                        {srv.type === 'builtin' ? 'Pre-built' : 'Custom'}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-relaxed">
                      {srv.description}
                    </p>
                  </div>
                  {srv.type !== 'builtin' && (
                    <button
                      onClick={() => handleDeleteCustom(srv.name)}
                      className="rounded p-1.5 text-slate-500 hover:bg-red-950/20 hover:text-red-400 transition"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Add Section */}
          <div className="rounded-xl border border-slate-850 bg-slate-900/10 p-5 space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-800/80 pb-2">
              <Terminal className="h-4 w-4 text-cyan-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">Register Custom MCP</h3>
            </div>

            <form onSubmit={handleRegisterCustom} className="space-y-3">
              <div>
                <label className="block text-[9px] font-bold text-slate-500 uppercase">Server Name</label>
                <input
                  type="text"
                  required
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  placeholder="e.g. postgres-mcp"
                  className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[9px] font-bold text-slate-500 uppercase">Command</label>
                <input
                  type="text"
                  required
                  value={customCmd}
                  onChange={(e) => setCustomCmd(e.target.value)}
                  placeholder="e.g. npx, python"
                  className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[9px] font-bold text-slate-500 uppercase">Arguments (Comma-separated)</label>
                <input
                  type="text"
                  value={customArgs}
                  onChange={(e) => setCustomArgs(e.target.value)}
                  placeholder="e.g. -y, @modelcontextprotocol/server-postgres"
                  className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[9px] font-bold text-slate-500 uppercase">Description (Optional)</label>
                <input
                  type="text"
                  value={customDesc}
                  onChange={(e) => setCustomDesc(e.target.value)}
                  placeholder="Provide details..."
                  className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none"
                />
              </div>

              <button
                type="submit"
                className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 py-2 text-xs font-bold text-white transition-all cursor-pointer"
              >
                <Plus className="h-3.5 w-3.5" /> Add Custom Server
              </button>
            </form>
          </div>
        </div>

        <div className="rounded-xl border border-amber-500/10 bg-amber-500/5 p-4 flex gap-3 text-xs text-amber-300 ring-1 ring-amber-500/10">
          <Shield className="h-5 w-5 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold">Swarm Governance Guardrails Active</span>
            <p className="text-slate-400 leading-relaxed text-[11px]">
              Any tool execution against these MCP resources matching destructive patterns (e.g. deletion, force pushes, drops) requires explicit Approve/Deny confirmation.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
