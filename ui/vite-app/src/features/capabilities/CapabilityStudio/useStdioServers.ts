import { useEffect, useState } from 'react';
import { apiClient } from '@/api/client';
import type { StdioResult, StdioServer } from './stdioTypes';

export function useStdioServers(onServersChanged?: () => void) {
  const [servers, setServers] = useState<StdioServer[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [tools, setTools] = useState<Record<string, unknown[]>>({});
  const [executing, setExecuting] = useState<string | null>(null);
  const [result, setResult] = useState<StdioResult | null>(null);

  const loadServers = async () => {
    setLoading(true);
    const res = await apiClient.get<{ servers: StdioServer[] }>('/mcp/stdio/servers');
    setServers(res.data?.servers || []);
    setLoading(false);
  };

  const register = async (form: { name: string; command: string; args: string; working_dir?: string }) => {
    const args = form.args.split(' ').filter(Boolean);
    await apiClient.post('/mcp/stdio/register', {
      name: form.name,
      command: form.command,
      args,
      working_dir: form.working_dir || undefined,
      description: `Stdio MCP: ${form.name}`
    });
    await loadServers();
    onServersChanged?.();
  };

  const remove = async (name: string) => {
    if (!confirm(`Stop and remove "${name}"?`)) return;
    await apiClient.delete(`/mcp/stdio/${name}`);
    await loadServers();
    onServersChanged?.();
  };

  const toggle = async (name: string) => {
    if (expanded === name) return setExpanded(null);
    setExpanded(name);
    if (tools[name]) return;
    const res = await apiClient.get<{ tools: unknown[] }>(`/mcp/stdio/${name}/tools`);
    setTools((prev) => ({ ...prev, [name]: res.data?.tools || [] }));
  };

  const runTool = async (serverName: string, toolName: string) => {
    const id = `${serverName}:${toolName}`;
    setExecuting(id);
    setResult(null);
    try {
      const res = await apiClient.post(`/mcp/stdio/${serverName}/execute`, { tool_name: toolName, arguments: {} });
      setResult({ id, status: 'success', data: res.data });
    } catch (error) {
      setResult({ id, status: 'error', data: error instanceof Error ? error.message : String(error) });
    } finally {
      setExecuting(null);
    }
  };

  useEffect(() => { loadServers(); }, []);
  return { servers, loading, expanded, tools, executing, result, loadServers, register, remove, toggle, runTool, setResult };
}
