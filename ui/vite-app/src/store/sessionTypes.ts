export interface Workspace {
  type: 'local' | 'git';
  slug: string;
  path?: string;
  url?: string;
  branch?: string;
}

export interface LLMConfig {
  model: string;
  api_key: string;
  base_url: string;
  extra_body: string;
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
}

export interface SessionState {
  sessionId: string;
  tenantId: string;
  userEmail: string;
  userRole: string;
  workspaces: Workspace[];
  plugins: { name: string; url: string }[];
  activeSkills: string[];
  status: 'idle' | 'connecting' | 'active' | 'error';
  llmConfig: LLMConfig;
  llmPreset: string;
  activeModelId: string;
  setSessionId: (id: string) => void;
  setActiveModelId: (id: string) => void;
  setUser: (email: string, role?: string) => void;
  setStatus: (s: SessionState['status']) => void;
  setWorkspaces: (w: Workspace[]) => void;
  addPlugin: (plugin: { name: string; url: string }) => void;
  removePlugin: (name: string) => void;
  toggleSkill: (skillId: string) => void;
  setLlmConfig: (config: Partial<LLMConfig>) => void;
  setLlmPreset: (preset: string) => void;
  ensureSession: (workspaces?: Workspace[]) => Promise<void>;
  addWorkspace: (ws: Workspace) => Promise<void>;
  removeWorkspace: (slug: string) => Promise<void>;
  reset: () => void;
  initLlmFromStorage: () => void;
}
