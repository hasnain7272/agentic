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
  status: 'idle' | 'connecting' | 'active' | 'error';
  llmConfig: LLMConfig;
  llmPreset: string;
  activeModelId: string;
  setSessionId: (id: string) => void;
  setActiveModelId: (id: string) => void;
  setUser: (email: string) => void;
  setStatus: (s: SessionState['status']) => void;
  setLlmConfig: (config: Partial<LLMConfig>) => void;
  setLlmPreset: (preset: string) => void;
  ensureSession: () => Promise<void>;
  reset: () => void;
  initLlmFromStorage: () => void;
}
