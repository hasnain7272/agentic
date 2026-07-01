import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { createSessionActions } from './sessionActions';
import type { SessionState, Workspace } from './sessionTypes';

export type { Workspace } from './sessionTypes';

const initialState = {
  sessionId: '',
  tenantId: '',
  userEmail: '',
  userRole: 'developer',
  workspaces: [],
  plugins: [],
  activeSkills: [],
  status: 'idle' as const,
  llmConfig: { model: 'gpt-4o', api_key: '', base_url: '', extra_body: '', temperature: 0.2, top_p: 0.95, max_tokens: 8192 },
  llmPreset: 'openai',
  activeModelId: '',
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
        };
      },
      partialize: (state) => ({
        sessionId: state.sessionId,
        tenantId: state.tenantId,
        userEmail: state.userEmail,
        userRole: state.userRole,
        workspaces: state.workspaces,
        plugins: state.plugins,
        activeSkills: state.activeSkills,
        llmConfig: { ...state.llmConfig, api_key: '' },
        llmPreset: state.llmPreset,
        activeModelId: state.activeModelId,
      }),
    },
  ),
);
