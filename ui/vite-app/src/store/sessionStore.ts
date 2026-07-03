import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { createSessionActions } from './sessionActions';
import type { SessionState } from './sessionTypes';

const initialState = {
  sessionId: '',
  tenantId: '',
  userEmail: '',
  status: 'idle' as const,
  llmConfig: { model: 'gpt-4o', api_key: '', base_url: '', extra_body: '', temperature: 0.2, top_p: 0.95, max_tokens: 8192 },
  llmPreset: 'openai',
  activeModelId: '',
  sessionByokConfig: null as SessionState['sessionByokConfig'],
};

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get, store) => ({
      ...initialState,
      ...createSessionActions(set, get, store),
    }),
    {
      name: 'ag-session',
      merge: (persisted, current) => {
        const stored = persisted as Partial<SessionState>;
        return {
          ...current,
          ...stored,
          llmConfig: { ...current.llmConfig, ...stored.llmConfig, api_key: '' },
          // Don't persist sessionByokConfig - it's session-scoped and should be cleared on new session
          sessionByokConfig: null,
        };
      },
      partialize: (state) => ({
        sessionId: state.sessionId,
        tenantId: state.tenantId,
        userEmail: state.userEmail,
        llmConfig: { ...state.llmConfig, api_key: '' },
        llmPreset: state.llmPreset,
        activeModelId: state.activeModelId,
        // Don't persist sessionByokConfig - it's session-scoped
      }),
    },
  ),
);
