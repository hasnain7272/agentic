import { Cpu, Server, KeyRound, EyeOff, Eye } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

export const PRESETS = [
  { id: 'nvidia-glm', label: 'GLM 5.1', provider: 'NVIDIA', model: 'z-ai/glm-5.1', base_url: 'https://integrate.api.nvidia.com/v1', hint: 'NVIDIA-hosted GLM. Fast streaming default for production chat.', color: 'text-green-400', temperature: 1, top_p: 1, max_tokens: 8192 },
  { id: 'nvidia-minimax', label: 'MiniMax M2.7', provider: 'NVIDIA', model: 'minimaxai/minimax-m2.7', base_url: 'https://integrate.api.nvidia.com/v1', hint: 'NVIDIA-hosted MiniMax. Use when GLM quality or style is not ideal.', color: 'text-lime-400', temperature: 1, top_p: 0.95, max_tokens: 8192 },
  { id: 'nvidia-qwen-coder', label: 'Qwen3 Coder 480B', provider: 'NVIDIA', model: 'qwen/qwen3-coder-480b-a35b-instruct', base_url: 'https://integrate.api.nvidia.com/v1', hint: 'NVIDIA-hosted Qwen3 Coder. Strong for code edits and repo reasoning.', color: 'text-cyan-400', temperature: 0.7, top_p: 0.8, max_tokens: 4096 },
  { id: 'openai', label: 'OpenAI GPT-4o', provider: 'OpenAI', model: 'gpt-4o', hint: 'Works with GPT-4o, GPT-4.1, o-series.', color: 'text-emerald-400', temperature: 0.2, top_p: 0.95, max_tokens: 8192 },
  { id: 'anthropic', label: 'Claude Sonnet', provider: 'Anthropic', model: 'claude-sonnet-4-20250514', hint: 'Works with Claude Opus, Sonnet, Haiku.', color: 'text-amber-400', temperature: 0.2, top_p: 0.95, max_tokens: 8192 },
  { id: 'ollama', label: 'Ollama Llama', provider: 'Local', model: 'ollama/llama3.3', base_url: 'http://localhost:11434', hint: 'Local Ollama.', color: 'text-sky-400', temperature: 0.2, top_p: 0.95, max_tokens: 4096 },
  { id: 'custom', label: 'Custom', provider: 'Custom', model: '', hint: 'Any OpenAI-compatible API.', color: 'text-violet-400', temperature: 0.2, top_p: 0.95, max_tokens: 8192 },
];

export function LLMSettings({ preset, setPreset, config, setConfig, existingKey, showKey, setShowKey }: any) {
  const llmConfig = useSessionStore((s) => s.llmConfig);
  const setLlmConfig = useSessionStore((s) => s.setLlmConfig);
  const currentPreset = PRESETS.find(p => p.id === preset) || PRESETS[0];

  const handleConfigChange = (key: string, value: string) => {
    const nextValue = ['temperature', 'top_p', 'max_tokens'].includes(key) ? Number(value) : value;
    setConfig((c: any) => ({ ...c, [key]: nextValue }));
    setLlmConfig({ [key]: nextValue });
  };

  const handlePresetSelect = (p: typeof PRESETS[0]) => {
    setPreset(p.id);
    setConfig((c: any) => ({ ...c, model: p.model, base_url: p.base_url || '', temperature: p.temperature, top_p: p.top_p, max_tokens: p.max_tokens }));
    setLlmConfig({ model: p.model, base_url: p.base_url || '', temperature: p.temperature, top_p: p.top_p, max_tokens: p.max_tokens });
  };

  return (
    <div className="p-6 pb-2">
      <label className="mb-4 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-slate-500/80">
        <Cpu className="h-3 w-3" /> Intelligence Provider
      </label>

      <div className="mb-2 px-1 text-[10px] font-bold uppercase tracking-widest text-slate-600">NVIDIA hosted</div>
      <div className="flex flex-wrap gap-1.5 mb-3">
        {PRESETS.filter(p => p.provider === 'NVIDIA').map(p => (
          <button key={p.id} onClick={() => handlePresetSelect(p)}
            className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition ${preset === p.id ? 'bg-slate-700/80 text-white ring-1 ring-slate-600' : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-300'}`}>
            {p.label}
          </button>
        ))}
      </div>
      <div className="mb-2 px-1 text-[10px] font-bold uppercase tracking-widest text-slate-600">Other providers</div>
      <div className="flex flex-wrap gap-1.5 mb-4">
        {PRESETS.filter(p => p.provider !== 'NVIDIA').map(p => (
          <button key={p.id} onClick={() => handlePresetSelect(p)}
            className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition ${preset === p.id ? 'bg-slate-700/80 text-white ring-1 ring-slate-600' : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-300'}`}>
            {p.label}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        <p className={`text-[11px] ${currentPreset.color} px-1`}>{currentPreset.hint}</p>
        <div>
          <label className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500"><Server className="h-3 w-3" />Model name</label>
          <input value={config.model} onChange={e => handleConfigChange('model', e.target.value)}
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
            placeholder="Defaults to provider auto-detection"
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
