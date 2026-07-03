import type { StateCreator } from 'zustand';
import { apiClient } from '@/api/client';
import type { SessionState } from './sessionTypes';

export const createSessionActions: StateCreator<SessionState, [], [], Pick<SessionState,
  'setSessionId' | 'setActiveModelId' | 'setUser' | 'setStatus' | 'setLlmConfig' | 'setLlmPreset' | 'initLlmFromStorage' | 'ensureSession' | 'reset'
>> = (set, get) => ({
  setSessionId: (id) => set({ sessionId: id, status: 'active' }),
  setActiveModelId: (id) => set({ activeModelId: id }),
  setUser: (email) => set({ userEmail: email }),
  setStatus: (status) => set({ status }),
  setLlmConfig: (config) => set((s) => ({ llmConfig: { ...s.llmConfig, ...config } })),
  setLlmPreset: (preset) => set({ llmPreset: preset }),
  initLlmFromStorage: () => {
    try {
      const raw = localStorage.getItem('llm_config');
      if (!raw) return;
      const parsed = JSON.parse(raw);
      const current = get().llmConfig;
      if (!current.model && parsed.config?.model) {
        set({ llmConfig: { ...current, ...parsed.config, api_key: '' }, llmPreset: parsed.preset });
      }
    } catch {}
  },
  ensureSession: async () => {
    if (!localStorage.getItem('auth_token')) return;
    const current = get();

    // If we already have a session ID from persistence, just verify it's active.
    if (current.sessionId) {
      if (!current.tenantId) set({ tenantId: 'local' });
      set({ status: 'active' });
      return;
    }

    // Default to session-less welcome screen
    set({ status: 'active', sessionId: '' });
  },
  reset: () => set({ sessionId: '', tenantId: '', userEmail: '', status: 'idle', llmConfig: { ...get().llmConfig, api_key: '' } }),
});
