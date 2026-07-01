export type ChatRole = 'user' | 'assistant' | 'tool' | 'system';

export interface ToolCall {
  function?: {
    name?: string;
    arguments?: string;
  };
  status?: string;
  progress?: number;
}

export interface Msg {
  id?: string;
  role: ChatRole;
  content: string;
  streaming?: boolean;
  reasoning?: string;
  tool_calls?: ToolCall[];
  metadata?: Record<string, any>;
  created_at?: string;
}

export interface ModelOption {
  id: string;
  label: string;
  name?: string;
  provider?: string;
  model: string;
  base_url?: string;
  is_configured?: boolean;
}

export interface ChatActivity {
  id: string;
  kind: 'thinking' | 'token' | 'tool' | 'approval' | 'done' | 'error';
  label: string;
  detail?: string;
}
