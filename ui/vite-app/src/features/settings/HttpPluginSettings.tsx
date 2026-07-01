import { useState } from 'react';
import { Plug } from 'lucide-react';
import { apiClient } from '@/api/client';
import { useSessionStore } from '@/store/sessionStore';

export function HttpPluginSettings() {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const addPlugin = useSessionStore((s) => s.addPlugin);

  const register = async () => {
    if (!name || !url) return;
    setLoading(true);
    try {
      await apiClient.post('/mcp/register', { name, description: `Plugin: ${name}`, endpoint_url: url });
      addPlugin({ name, url });
      setName('');
      setUrl('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-dashed border-slate-700 bg-slate-800/30 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Plug className="h-3.5 w-3.5 text-cyan-400" />
        <h4 className="text-xs font-semibold text-slate-200">Register HTTP Plugin</h4>
      </div>
      <div className="flex flex-col gap-2 xl:flex-row">
        <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Plugin name" className="rounded-lg border border-slate-700/60 bg-slate-900/50 px-3 py-1.5 text-xs text-slate-100 outline-none transition focus:border-cyan-500/40 xl:w-1/3" />
        <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="Endpoint URL" className="flex-1 rounded-lg border border-slate-700/60 bg-slate-900/50 px-3 py-1.5 text-xs text-slate-100 outline-none transition focus:border-cyan-500/40" />
        <button onClick={register} disabled={loading || !name || !url} className="rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-cyan-500 disabled:opacity-50">
          {loading ? 'Loading...' : 'Hot Load'}
        </button>
      </div>
    </div>
  );
}
