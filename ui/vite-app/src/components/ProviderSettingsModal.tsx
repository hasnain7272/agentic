/**
 * ProviderSettingsModal — BYOK Configuration UI.
 * Ultra-premium, sub-100 line implementation utilizing modular settings panes.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { apiClient } from '@/api/client';
import { useSessionStore } from '@/store/sessionStore';
import { PRESETS, LLMSettings } from '@/features/settings/LLMSettings';
import { GitSettings } from '@/features/settings/GitSettings';
import { CapabilitySettings } from '@/features/settings/CapabilitySettings';
import { ProviderSettingsFooter, ProviderSettingsHeader } from '@/components/ProviderSettingsChrome';

interface Props { open: boolean; onClose: () => void; targetSessionId?: string; }

export function ProviderSettingsModal({ open, onClose, targetSessionId }: Props) {
  const llmConfig = useSessionStore(s => s.llmConfig);
  const llmPreset = useSessionStore(s => s.llmPreset);
  const setLlmConfig = useSessionStore(s => s.setLlmConfig);
  const setLlmPreset = useSessionStore(s => s.setLlmPreset);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [preset, setPreset] = useState(llmPreset || PRESETS[0].id);
  const [config, setConfig] = useState(llmConfig);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [existingKey, setExistingKey] = useState('');

  useEffect(() => {
    setConfig(llmConfig);
    setPreset(llmPreset || PRESETS[0].id);
  }, [llmConfig, llmPreset]);

  const loadConfig = useCallback(async () => {
    try {
      const res = await apiClient.get<any>(`/settings/byok`);
      const list = res.data?.data || [];
      const activeId = targetSessionId || useSessionStore.getState().activeModelId || PRESETS[0].id;
      
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
    const el = dialogRef.current;
    if (!el) return;
    if (open) {
      if (!el.open) { el.showModal(); loadConfig(); }
    } else {
      if (el.open) el.close();
    }
  }, [open, loadConfig]);

  const handleSave = async () => {
    setSaving(true); setError('');
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
    } catch (e: any) { setError(e.message || 'Network error.'); } finally { setSaving(false); }
  };

  if (!open) return null;

  return (
    <dialog ref={dialogRef} onCancel={onClose}
      className="fixed inset-0 z-50 m-auto h-auto w-full max-w-xl rounded-2xl border border-slate-700/60 bg-slate-900/95 p-0 text-slate-100 shadow-2xl shadow-black/60 backdrop:bg-black/70 backdrop:backdrop-blur-sm scale-in">
      <div className="flex flex-col max-h-[85vh]">
        <ProviderSettingsHeader onClose={onClose} />

        <div className="flex-1 overflow-y-auto min-h-0 custom-scrollbar">
          <LLMSettings preset={preset} setPreset={setPreset} config={config} setConfig={setConfig} existingKey={existingKey} showKey={showKey} setShowKey={setShowKey} />
          <div className="mx-6 my-4 h-px bg-slate-800/60" />
          <GitSettings />
          <div className="mx-6 my-4 h-px bg-slate-800/60" />
          <CapabilitySettings />
        </div>

        {error && <div className="mx-6 mb-4 rounded-lg bg-red-900/30 px-3 py-2 text-xs text-red-400 ring-1 ring-red-800/40">{error}</div>}

        <ProviderSettingsFooter saving={saving} saved={saved} onClose={onClose} onSave={handleSave} />
      </div>
    </dialog>
  );
}
