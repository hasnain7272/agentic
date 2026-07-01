import { useState } from 'react';
import { Plug } from 'lucide-react';
import type { ToolInfo } from './types';
import { useSessionStore } from '@/store/sessionStore';
import { apiClient } from '@/api/client';

interface Props {
  plugins: ToolInfo[];
  onPluginsChanged: () => void;
}

export function PluginsTab({ plugins, onPluginsChanged }: Props) {
  const [pluginName, setPluginName] = useState('');
  const [pluginUrl, setPluginUrl] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const registerPlugin = async () => {
    if (!pluginName.trim() || !pluginUrl.trim() || saving) return;
    if (!/^https?:\/\//.test(pluginUrl.trim())) {
      setMessage('Endpoint must start with http:// or https://');
      return;
    }
    setSaving(true);
    setMessage('');
    const res = await apiClient.post<{ message: string }>('/mcp/register', {
      name: pluginName.trim(),
      description: `Dynamic plugin for ${pluginName.trim()}`,
      endpoint_url: pluginUrl.trim(),
      parameters: [],
    });
    setSaving(false);
    if (res.data) {
      useSessionStore.getState().addPlugin({ name: pluginName.trim(), url: pluginUrl.trim() });
      setPluginName('');
      setPluginUrl('');
      setMessage(res.data.message || 'Plugin registered.');
      onPluginsChanged();
    } else {
      setMessage(res.error || 'Failed to register plugin.');
    }
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="space-y-3">
        {plugins.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-500">
            No dynamic plugins are registered yet.
          </div>
        )}
        {plugins.map((plugin) => (
          <div key={plugin.name} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="flex items-center gap-2">
              <Plug className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-semibold text-slate-100">{plugin.name}</span>
              {plugin.endpoint_url && (
                <span className="text-[10px] text-slate-500 truncate max-w-[200px]">{plugin.endpoint_url}</span>
              )}
            </div>
            <p className="mt-2 text-sm text-slate-400">{plugin.description}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {plugin.parameters.map((param) => (
                <span key={`${plugin.name}-${param.name}`} className="rounded-lg bg-slate-950 px-2.5 py-1 text-[11px] text-slate-400 ring-1 ring-slate-800">
                  {param.name}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 h-fit">
        <h3 className="text-sm font-semibold text-slate-100">Register MCP Plugin</h3>
        <p className="mt-2 text-sm text-slate-400">
          Hot-load a remote capability into the active runtime. For sandbox-to-local, use{' '}
          <code className="text-violet-400 font-mono text-xs">http://host.docker.internal:PORT</code>.
        </p>
        <div className="mt-4 space-y-3">
          <input
            value={pluginName}
            onChange={(e) => setPluginName(e.target.value)}
            placeholder="Plugin name"
            className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-violet-600/40"
          />
          <input
            value={pluginUrl}
            onChange={(e) => setPluginUrl(e.target.value)}
            placeholder="https://plugin.example.com/run"
            className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-violet-600/40"
          />
          <button
            onClick={registerPlugin}
            disabled={saving}
            className="w-full rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:opacity-50"
          >
            {saving ? 'Registering...' : 'Register Plugin'}
          </button>
        </div>
        {message && (
          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/80 px-3 py-2 text-xs text-slate-400">
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
