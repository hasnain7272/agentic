export interface StdioServer {
  name: string;
  status: string;
  tool_count: number;
  error_message?: string;
  command?: string;
  args?: string[];
  description?: string;
}

export interface StdioResult {
  id: string;
  status: 'success' | 'error';
  data: unknown;
}
