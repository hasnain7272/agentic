import { Cpu, Server, KeyRound, EyeOff, Eye } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

export const PRESETS = [
  { id: 'custom', label: 'Custom', provider: 'Custom', model: 'gpt-4o-mini', base_url: '', hint: 'Configure any custom OpenAI-compatible API.', color: 'text-violet-400', temperature: 0.2, top_p: 0.95, max_tokens: 8192 }
];

export function LLMSettings({ preset, setPreset, config, setConfig, existingKey, showKey, setShowKey }: any) {
  const llmConfig = useSessionStore((s) => s.llmConfig);
  const setLlmConfig = useSessionStore((s) => s.setLlmConfig);

  const handleConfigChange = (key: string, value: string) => {
    const nextValue = ['temperature', 'top_p', 'max_tokens'].includes(key) ? Number(value) : value;
    setConfig((c: any) => ({ ...c, [key]: nextValue }));
    setLlmConfig({ [key]: nextValue });
  };

  return (
    <div className="p-6 pb-2">
      <label className="mb-4 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-slate-500/80">
        <Cpu className="h-3 w-3" /> Custom API Provider
      </label>

      <div className="space-y-4">
        <p className="text-[11px] text-violet-400 px-1">Configure your custom OpenAI-compatible API endpoint (e.g. OpenAI, OpenRouter, Anthropic, or local endpoints).</p>
        
        <div>
          <label className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500"><Server className="h-3 w-3" />Model Name</label>
          <input value={config.model} onChange={e => handleConfigChange('model', e.target.value)}
            placeholder="gpt-4o-mini"
            className="w-full rounded-lg border border-slate-700/60 bg-slate-800/50 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-cyan-600/60 focus:ring-1 focus:ring-cyan-600/30 transition font-mono" />
        </div>
        <div>
          <label className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500"><KeyRound className="h-3 w-3" />API Key</label>
          {existingKey && !config.api_key && <div className="mb-1.5 rounded-md bg-emerald-900/20 px-2.5 py-1 text-[11px] text-emerald-400 ring-1 ring-emerald-800/40">Current: <span className="font-mono">{existingKey}</span></div>}
          {llmConfig.api_key && !config.api_key && (
            <div className="mb-1.5 rounded-md bg-emerald-900/20 px-2.5 py-1 text-[11px] text-emerald-400 ring-1 ring-emerald-800/40">Saved: <span className="font-mono">••••{llmConfig.api_key.slice(-4)}</span></div>
          )}
          <div className="relative">
            <input type={showKey ? 'text' : 'password'} value={config.api_key} onChange={e => handleConfigChange('api_key', e.target.value)}
              placeholder={existingKey || llmConfig.api_key ? 'Enter new key to replace...' : 'sk-...'}
              className="w-full rounded-lg border border-slate-700/60 bg-slate-800/50 px-3 py-2 pr-10 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-cyan-600/60 focus:ring-1 focus:ring-cyan-600/30 transition font-mono" />
            <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:text-slate-300 transition">
              {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
        <div>
          <label className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Base URL <span className="ml-auto font-normal normal-case text-slate-600">optional</span></label>
          <input value={config.base_url} onChange={e => handleConfigChange('base_url', e.target.value)}
            placeholder="https://api.openai.com/v1"
            className="w-full rounded-lg border border-slate-700/60 bg-slate-800/50 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-cyan-600/60 focus:ring-1 focus:ring-cyan-600/30 transition font-mono" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="min-w-0">
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-slate-500">Temp</label>
            <input type="number" min="0" max="2" step="0.1" value={config.temperature ?? 0.2} onChange={e => handleConfigChange('temperature', e.target.value)}
              className="w-full rounded-lg border border-slate-700/60 bg-slate-800/50 px-2.5 py-2 text-sm text-slate-100 outline-none focus:border-cyan-600/60 focus:ring-1 focus:ring-cyan-600/30 transition font-mono" />
          </div>
          <div className="min-w-0">
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-slate-500">Top P</label>
            <input type="number" min="0" max="1" step="0.05" value={config.top_p ?? 0.95} onChange={e => handleConfigChange('top_p', e.target.value)}
              className="w-full rounded-lg border border-slate-700/60 bg-slate-800/50 px-2.5 py-2 text-sm text-slate-100 outline-none focus:border-cyan-600/60 focus:ring-1 focus:ring-cyan-600/30 transition font-mono" />
          </div>
          <div className="min-w-0">
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-slate-500">Max Tokens</label>
            <input type="number" min="256" max="32768" step="256" value={config.max_tokens ?? 8192} onChange={e => handleConfigChange('max_tokens', e.target.value)}
              className="w-full rounded-lg border border-slate-700/60 bg-slate-800/50 px-2.5 py-2 text-sm text-slate-100 outline-none focus:border-cyan-600/60 focus:ring-1 focus:ring-cyan-600/30 transition font-mono" />
          </div>
        </div>
      </div>
    </div>
  );
}
