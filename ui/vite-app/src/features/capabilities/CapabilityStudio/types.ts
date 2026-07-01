export type ToolParameter = {
  name: string;
  type: string;
  description: string;
  required: boolean;
};

export type ToolInfo = {
  name: string;
  description: string;
  category: string;
  origin: 'builtin' | 'plugin';
  requires_sandbox: boolean;
  parameters: ToolParameter[];
  endpoint_url?: string;
};

export type SkillInfo = {
  id: string;
  name: string;
  description: string;
  prompt: string;
  tools: ToolInfo[];
  missing_tools?: string[];
  ready?: boolean;
  coverage?: number;
};

export type PluginMetrics = {
  name: string;
  description: string;
  endpoint_url: string;
  status: string;
  total_calls: number;
  failed_calls: number;
  success_rate: number;
  avg_latency_ms: number;
  last_called: number | null;
};

export type DashboardResponse = {
  status: string;
  plugins: PluginMetrics[];
  total_count: number;
  healthy_count: number;
  circuit_open_count: number;
};

export type CatalogResponse = {
  status?: string;
  tools: ToolInfo[];
  plugins: ToolInfo[];
  skills: SkillInfo[];
  categories: { id: string; label: string; count: number }[];
  summary?: CapabilitySummary;
};

export type CapabilitySummary = {
  tools: number;
  skills: number;
  plugins: number;
  categories: number;
  ready_skills: number;
  missing_skill_tools: number;
  stdio_servers?: number;
  stdio_running?: number;
};
