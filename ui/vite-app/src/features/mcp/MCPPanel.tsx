import { useEffect, useState } from 'react';
import { useSessionStore } from '@/store/sessionStore';
import { apiClient } from '@/api/client';
import { Cpu, Terminal, Plus, Trash2, Globe, Shield, CheckCircle, Loader2 } from 'lucide-react';
import { useToastStore } from '@/components/Toast';

interface McoServer {
  name: string;
  command: string;
  args: string[];
  working_dir?: string;
  description?: string;
  status?: string;
}

interface HttpPlugin {
  name: string;
  endpoint_url: string;
  description?: string;
}

export function MCPPanel() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const addToast = useToastStore((s) => s.addToast);

  const [servers, setServers] = useState<McoServer[]>([]);
  const [plugins, setPlugins] = useState<HttpPlugin[]>([]);
  const [loading, setLoading] = useState(false);

  // Stdio form state
  const [stdName, setStdName] = useState('');
  const [stdCmd, setStdCmd] = useState('');
  const [stdArgs, setStdArgs] = useState('');
  const [stdWd, setStdWd] = useState('');
  const [stdDesc, setStdDesc] = useState('');

  // HTTP form state
  const [httpName, setHttpName] = useState('');
  const [httpUrl, setHttpUrl] = useState('');
  const [httpDesc, setHttpDesc] = useState('');

  const loadMcp = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await apiClient.get<any>(`/mcp/catalog?session_id=${sessionId}`);
      if (res.data) {
        // Retrieve dynamic stdio servers & HTTP plugins registered under this session
        const stdioRes = await apiClient.get<any>(`/mcp/stdio/servers?session_id=${sessionId}`);
        setServers(stdioRes.data?.servers || []);
        
        setPlugins(res.data.plugins || []);
      }
    } catch (e) {
      console.error('Failed to load MCP config', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMcp();
  }, [sessionId]);

  const handleRegisterStdio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionId || !stdName || !stdCmd) return;
    try {
      const payload = {
        session_id: sessionId,
        name: stdName,
        command: stdCmd,
        args: stdArgs.split(',').map(s => s.trim()).filter(Boolean),
        working_dir: stdWd || undefined,
        description: stdDesc || undefined,
      };
      const res = await apiClient.post<any>('/mcp/stdio/register', payload);
      if (res.data?.status === 'success' || res.status !== 'error') {
        addToast('success', `Stdio MCP server '${stdName}' registered!`);
        setStdName('');
        setStdCmd('');
        setStdArgs('');
        setStdWd('');
        setStdDesc('');
        loadMcp();
      }
    } catch (err: any) {
      addToast('error', err.message || 'Failed to register server');
    }
  };

  const handleRegisterHttp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionId || !httpName || !httpUrl) return;
    try {
      const payload = {
        session_id: sessionId,
        name: httpName,
        endpoint_url: httpUrl,
        description: httpDesc || undefined,
      };
      const res = await apiClient.post<any>('/mcp/register', payload);
      if (res.data?.status === 'success' || res.status !== 'error') {
        addToast('success', `HTTP MCP plugin '${httpName}' registered!`);
        setHttpName('');
        setHttpUrl('');
        setHttpDesc('');
        loadMcp();
      }
    } catch (err: any) {
      addToast('error', err.message || 'Failed to register plugin');
    }
  };

  const handleDeleteStdio = async (name: string) => {
    if (!sessionId) return;
    try {
      await apiClient.delete(`/mcp/stdio/${name}?session_id=${sessionId}`);
      addToast('success', `MCP server '${name}' removed.`);
      loadMcp();
    } catch (err: any) {
      addToast('error', err.message || 'Failed to remove server');
    }
  };

  const handleDeleteHttp = async (name: string) => {
    if (!sessionId) return;
    try {
      await apiClient.delete(`/mcp/${name}?session_id=${sessionId}`);
      addToast('success', `HTTP Plugin '${name}' removed.`);
      loadMcp();
    } catch (err: any) {
      addToast('error', err.message || 'Failed to remove plugin');
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
            <p className="text-xs text-slate-500">Govern tools, stdio servers, and remote HTTP plugins at the session level.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Stdio Servers Section */}
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/20 p-5 space-y-4">
              <div className="flex items-center gap-2 border-b border-slate-800/80 pb-2">
                <Terminal className="h-4 w-4 text-cyan-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">Stdio MCP Servers</h3>
              </div>

              <form onSubmit={handleRegisterStdio} className="space-y-3">
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Server Name</label>
                  <input
                    type="text"
                    required
                    value={stdName}
                    onChange={(e) => setStdName(e.target.value)}
                    placeholder="e.g. filesystem-mcp"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Command</label>
                  <input
                    type="text"
                    required
                    value={stdCmd}
                    onChange={(e) => setStdCmd(e.target.value)}
                    placeholder="e.g. node, python, npx"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Arguments (Comma-separated)</label>
                  <input
                    type="text"
                    value={stdArgs}
                    onChange={(e) => setStdArgs(e.target.value)}
                    placeholder="e.g. @modelcontextprotocol/server-filesystem, /path/to/share"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Working Dir (Optional)</label>
                  <input
                    type="text"
                    value={stdWd}
                    onChange={(e) => setStdWd(e.target.value)}
                    placeholder="e.g. d:/workspace"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Description (Optional)</label>
                  <input
                    type="text"
                    value={stdDesc}
                    onChange={(e) => setStdDesc(e.target.value)}
                    placeholder="Provide description..."
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>

                <button
                  type="submit"
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 py-2 text-xs font-bold text-white transition-all cursor-pointer shadow-lg shadow-cyan-900/10"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Stdio Server
                </button>
              </form>
            </div>

            {/* List stdio */}
            <div className="space-y-2">
              {servers.map((srv) => (
                <div key={srv.name} className="flex items-center justify-between rounded-xl border border-slate-800 bg-[#0f0f11] p-3 text-xs">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white">{srv.name}</span>
                      <span className="rounded bg-emerald-900/20 text-emerald-400 border border-emerald-800/30 px-1 py-0.5 text-[9px] font-mono uppercase">
                        {srv.status || 'Active'}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500 font-mono max-w-xs truncate">
                      {srv.command} {srv.args.join(' ')}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDeleteStdio(srv.name)}
                    className="rounded p-1.5 text-slate-500 hover:bg-red-950/20 hover:text-red-400 transition"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              {servers.length === 0 && (
                <div className="text-center py-6 border border-dashed border-slate-800 rounded-xl text-slate-600 text-xs">
                  No stdio servers configured for this session.
                </div>
              )}
            </div>
          </div>

          {/* HTTP Plugins Section */}
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/20 p-5 space-y-4">
              <div className="flex items-center gap-2 border-b border-slate-800/80 pb-2">
                <Globe className="h-4 w-4 text-emerald-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">HTTP/HTTPS Plugins</h3>
              </div>

              <form onSubmit={handleRegisterHttp} className="space-y-3">
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Plugin Name</label>
                  <input
                    type="text"
                    required
                    value={httpName}
                    onChange={(e) => setHttpName(e.target.value)}
                    placeholder="e.g. weather-plugin"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Endpoint URL</label>
                  <input
                    type="url"
                    required
                    value={httpUrl}
                    onChange={(e) => setHttpUrl(e.target.value)}
                    placeholder="e.g. https://api.mcp-weather.com/endpoint"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Description (Optional)</label>
                  <input
                    type="text"
                    value={httpDesc}
                    onChange={(e) => setHttpDesc(e.target.value)}
                    placeholder="e.g. Queries weather information"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>

                <button
                  type="submit"
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 py-2 text-xs font-bold text-white transition-all cursor-pointer shadow-lg shadow-emerald-900/10"
                >
                  <Plus className="h-3.5 w-3.5" /> Add HTTP Plugin
                </button>
              </form>
            </div>

            {/* List HTTP */}
            <div className="space-y-2">
              {plugins.map((plg) => (
                <div key={plg.name} className="flex items-center justify-between rounded-xl border border-slate-800 bg-[#0f0f11] p-3 text-xs">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white">{plg.name}</span>
                      <span className="rounded bg-cyan-900/20 text-cyan-400 border border-cyan-800/30 px-1 py-0.5 text-[9px] font-mono uppercase">
                        HTTP
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500 truncate max-w-xs">{plg.endpoint_url}</p>
                  </div>
                  <button
                    onClick={() => handleDeleteHttp(plg.name)}
                    className="rounded p-1.5 text-slate-500 hover:bg-red-950/20 hover:text-red-400 transition"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              {plugins.length === 0 && (
                <div className="text-center py-6 border border-dashed border-slate-800 rounded-xl text-slate-600 text-xs">
                  No HTTP plugins configured for this session.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Governance message */}
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 flex gap-3 text-xs text-amber-300 ring-1 ring-amber-500/10">
          <Shield className="h-5 w-5 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold">Governed Environment</span>
            <p className="text-slate-400 leading-relaxed text-[11px]">
              Any tool execution requested by the agent loop against these MCP resources will require real-time user approval.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
