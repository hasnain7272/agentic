import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/api/client';
import { useSessionStore } from '@/store/sessionStore';
import { PRESETS, LLMSettings } from '@/features/settings/LLMSettings';
import { Loader2, Check } from 'lucide-react';

export function InlineSettingsTab() {
  const llmConfig = useSessionStore(s => s.llmConfig);
  const llmPreset = useSessionStore(s => s.llmPreset);
  const setLlmConfig = useSessionStore(s => s.setLlmConfig);
  const setLlmPreset = useSessionStore(s => s.setLlmPreset);

  const [preset, setPreset] = useState(llmPreset || PRESETS[0].id);
  const [config, setConfig] = useState(llmConfig);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [existingKey, setExistingKey] = useState('');

  const loadConfig = useCallback(async () => {
    try {
      const res = await apiClient.get<any>(`/settings/byok`);
      const list = res.data?.data || [];
      const activeId = useSessionStore.getState().activeModelId || PRESETS[0].id;
      
      const currentByom = list.find((b: any) => b.id === activeId);
      if (currentByom) {
        setExistingKey(currentByom.is_configured ? 'Stored in backend' : '');
        setConfig(c => ({
          ...c,
          model: currentByom.model || c.model,
          base_url: currentByom.base_url || '',
          api_key: '',
          temperature: currentByom.temperature ?? c.temperature ?? 0.2,
          top_p: currentByom.top_p ?? c.top_p ?? 0.95,
          max_tokens: currentByom.max_tokens ?? c.max_tokens ?? 8192,
        }));
        setPreset(currentByom.id);
      } else {
        const presetObj = PRESETS.find(p => p.id === activeId) || PRESETS[0];
        setExistingKey('');
        setConfig({
          model: presetObj.model || '',
          base_url: presetObj.base_url || '',
          api_key: '',
          temperature: presetObj.temperature ?? 0.2,
          top_p: presetObj.top_p ?? 0.95,
          max_tokens: presetObj.max_tokens ?? 8192,
        });
        setPreset(presetObj.id);
      }
    } catch (e) {
      console.error('Failed to load session config', e);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const presetObj = PRESETS.find(p => p.id === preset) || PRESETS[0];

      const payload: Record<string, any> = {
        id: preset,
        name: presetObj.label,
        provider: presetObj.provider,
        model: config.model,
        api_key: config.api_key || '',
        base_url: config.base_url || null,
        temperature: Number(config.temperature ?? presetObj.temperature ?? 0.2),
        top_p: Number(config.top_p ?? presetObj.top_p ?? 0.95),
        max_tokens: Number(config.max_tokens ?? presetObj.max_tokens ?? 8192),
      };

      const res = await apiClient.post<any>(`/settings/byok`, payload);
      if (res.status !== 'error' && res.data?.status === 'success') {
        setSaved(true);
        useSessionStore.getState().setActiveModelId(preset);
        setLlmPreset(preset);
        setLlmConfig({
          model: payload.model,
          base_url: payload.base_url || '',
          api_key: '',
          temperature: payload.temperature,
          top_p: payload.top_p,
          max_tokens: payload.max_tokens,
        });
        setConfig(c => ({ ...c, api_key: '' }));
        
        window.dispatchEvent(new Event('refresh-settings'));
        
        setTimeout(() => setSaved(false), 2000);
        loadConfig();
      } else {
        setError(res.error || 'Failed to save.');
      }
    } catch (e: any) {
      setError(e.message || 'Network error.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl p-6">
      <div className="rounded-2xl border border-slate-800 bg-[#0c0c0e] shadow-xl">
        <div className="border-b border-[#1e1e1e] px-6 py-4">
          <h3 className="text-sm font-semibold text-slate-100">LLM Provider Configuration</h3>
          <p className="text-[11px] text-slate-500 mt-1">Configure parameters and credentials for the AI agent loop.</p>
        </div>

        <LLMSettings
          preset={preset}
          setPreset={setPreset}
          config={config}
          setConfig={setConfig}
          existingKey={existingKey}
          showKey={showKey}
          setShowKey={setShowKey}
        />

        {error && (
          <div className="mx-6 mb-4 rounded-lg bg-red-900/30 px-3 py-2 text-xs text-red-400 ring-1 ring-red-800/40">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-3 border-t border-[#1e1e1e] bg-slate-900/10 px-6 py-4 rounded-b-2xl">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-50 cursor-pointer"
          >
            {saving ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Saving...
              </>
            ) : saved ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-300" />
                Saved!
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
