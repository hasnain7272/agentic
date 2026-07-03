import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/api/client';
import { useSessionStore } from '@/store/sessionStore';
import { Loader2, Check, Plus, Trash2, Settings, Server, KeyRound, EyeOff, Eye, ShieldCheck } from 'lucide-react';
import { useToastStore } from '@/components/Toast';

interface BYOKConfig {
  id: string;
  name: string;
  provider: string;
  model: string;
  base_url?: string;
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  is_configured?: boolean;
}

export function InlineSettingsTab() {
  const activeModelId = useSessionStore((s) => s.activeModelId);
  const setActiveModelId = useSessionStore((s) => s.setActiveModelId);
  const addToast = useToastStore((s) => s.addToast);

  const [configs, setConfigs] = useState<BYOKConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [showKey, setShowKey] = useState(false);

  // Form states
  const [name, setName] = useState('');
  const [provider, setProvider] = useState('OpenAI');
  const [model, setModel] = useState('gpt-4o-mini');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [temp, setTemp] = useState(0.2);
  const [topP, setTopP] = useState(0.95);
  const [maxTokens, setMaxTokens] = useState(8192);

  const loadConfigs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<any>('/settings/byok');
      const list = res.data?.data || [];
      setConfigs(list);
    } catch (e) {
      console.error('Failed to load configs', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  const handleCreateOrUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const id = editingId || `byok-${Math.random().toString(36).substring(2, 11)}`;
      const payload = {
        id,
        name,
        provider,
        model,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        temperature: Number(temp),
        top_p: Number(topP),
        max_tokens: Number(maxTokens),
      };

      const res = await apiClient.post<any>('/settings/byok', payload);
      if (res.data?.status === 'success' || res.status !== 'error') {
        addToast('success', editingId ? 'Configuration updated!' : 'New configuration added!');
        resetForm();
        loadConfigs();
        
        // If it's a new config or editing active config, make it active
        if (!activeModelId || editingId === activeModelId) {
          setActiveModelId(id);
        }
      }
    } catch (err: any) {
      addToast('error', err.message || 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (cfg: BYOKConfig) => {
    setEditingId(cfg.id);
    setName(cfg.name);
    setProvider(cfg.provider);
    setModel(cfg.model);
    setApiKey('');
    setBaseUrl(cfg.base_url || '');
    setTemp(cfg.temperature ?? 0.2);
    setTopP(cfg.top_p ?? 0.95);
    setMaxTokens(cfg.max_tokens ?? 8192);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this configuration?')) return;
    try {
      await apiClient.delete(`/settings/byok/${id}`);
      addToast('success', 'Configuration deleted.');
      if (activeModelId === id) {
        setActiveModelId('');
      }
      loadConfigs();
    } catch (err: any) {
      addToast('error', err.message || 'Failed to delete');
    }
  };

  const resetForm = () => {
    setEditingId(null);
    setName('');
    setProvider('OpenAI');
    setModel('gpt-4o-mini');
    setApiKey('');
    setBaseUrl('');
    setTemp(0.2);
    setTopP(0.95);
    setMaxTokens(8192);
    setShowForm(false);
  };

  return (
    <div className="mx-auto max-w-3xl p-6 text-slate-200">
      <div className="space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-cyan-500/10 p-2 text-cyan-400">
              <Settings className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">LLM Settings (BYOK)</h2>
              <p className="text-xs text-slate-500">Manage LLM configurations and credentials. Selected keys persist at user-level.</p>
            </div>
          </div>
          {!showForm && (
            <button
              onClick={() => { resetForm(); setShowForm(true); }}
              className="flex items-center gap-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-white transition-all cursor-pointer"
            >
              <Plus className="h-4 w-4" /> Add Configuration
            </button>
          )}
        </div>

        {showForm && (
          <div className="rounded-2xl border border-slate-800 bg-[#0c0c0e] p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-slate-100">
              {editingId ? 'Edit Configuration' : 'Add LLM Configuration'}
            </h3>

            <form onSubmit={handleCreateOrUpdate} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Configuration Name</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. My OpenRouter Key"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Provider / Tag</label>
                  <input
                    type="text"
                    required
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    placeholder="e.g. OpenAI, Anthropic, OpenRouter"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Model Name</label>
                  <input
                    type="text"
                    required
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="e.g. gpt-4o-mini, claude-3-5-sonnet"
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">API Key</label>
                  <div className="relative mt-1">
                    <input
                      type={showKey ? 'text' : 'password'}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={editingId ? '•••••••• (Leave empty to keep existing)' : 'sk-...'}
                      className="w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 pr-10 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey(!showKey)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition"
                    >
                      {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-semibold text-slate-500 uppercase">
                  Base URL <span className="text-[9px] text-slate-600 normal-case">(optional)</span>
                </label>
                <input
                  type="url"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="e.g. https://openrouter.ai/api/v1"
                  className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all font-mono"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Temp</label>
                  <input
                    type="number"
                    min="0"
                    max="2"
                    step="0.1"
                    value={temp}
                    onChange={(e) => setTemp(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Top P</label>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value={topP}
                    onChange={(e) => setTopP(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-500 uppercase">Max Tokens</label>
                  <input
                    type="number"
                    min="256"
                    max="32768"
                    step="256"
                    value={maxTokens}
                    onChange={(e) => setMaxTokens(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t border-slate-800/80 pt-4">
                <button
                  type="button"
                  onClick={resetForm}
                  className="rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-2 text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-xs font-semibold text-white transition disabled:opacity-50"
                >
                  {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                  Save Configuration
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Configurations List */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Your Configurations</h3>
          {configs.map((cfg) => {
            const isActive = activeModelId === cfg.id;
            return (
              <div
                key={cfg.id}
                className={`flex flex-col sm:flex-row items-start sm:items-center justify-between rounded-2xl border p-4 transition-all gap-4 ${
                  isActive
                    ? 'border-emerald-500/30 bg-emerald-500/5 shadow-md shadow-emerald-950/10'
                    : 'border-slate-800 bg-[#0f0f11] hover:border-slate-700'
                }`}
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-100">{cfg.name}</span>
                    <span className="rounded bg-slate-800 text-slate-400 border border-slate-700/50 px-1.5 py-0.5 text-[9px] font-mono uppercase">
                      {cfg.provider}
                    </span>
                    {isActive && (
                      <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-bold bg-emerald-950/20 px-2 py-0.5 rounded-full border border-emerald-800/30">
                        <Check className="h-3 w-3" /> Active
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
                    <span className="font-mono">{cfg.model}</span>
                    {cfg.base_url && (
                      <span className="truncate max-w-xs font-mono">{cfg.base_url}</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                  {!isActive && (
                    <button
                      onClick={() => {
                        setActiveModelId(cfg.id);
                        addToast('success', `Active config set to '${cfg.name}'`);
                      }}
                      className="rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900/50 hover:bg-slate-900 px-2.5 py-1.5 text-xs font-semibold text-slate-300 hover:text-white transition cursor-pointer"
                    >
                      Make Active
                    </button>
                  )}
                  <button
                    onClick={() => handleEdit(cfg)}
                    className="rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900/50 hover:bg-slate-900 px-2.5 py-1.5 text-xs font-semibold text-slate-300 hover:text-white transition cursor-pointer"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(cfg.id)}
                    className="rounded-lg border border-slate-800 hover:border-red-900/50 bg-slate-900/50 hover:bg-red-950/20 p-2 text-slate-500 hover:text-red-400 transition cursor-pointer"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            );
          })}

          {configs.length === 0 && !loading && (
            <div className="text-center py-12 border border-dashed border-slate-800 rounded-2xl text-slate-500 text-xs">
              No configurations added yet. Click "Add Configuration" above to get started.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
