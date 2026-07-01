import { AlertCircle, CheckCircle, ChevronDown, ChevronRight, Clock, Play, RefreshCw, Terminal } from 'lucide-react';
import type { StdioResult, StdioServer } from './stdioTypes';

interface ToolItem { name?: string; description?: string; }
interface Props {
  servers: StdioServer[];
  loading: boolean;
  expanded: string | null;
  tools: Record<string, unknown[]>;
  executing: string | null;
  result: StdioResult | null;
  onRefresh: () => void;
  onToggle: (name: string) => void;
  onRemove: (name: string) => void;
  onRun: (serverName: string, toolName: string) => void;
}

const statusColor = (status: string) => status === 'running' ? 'bg-emerald-500' : status === 'error' ? 'bg-red-500' : 'bg-amber-500';
const statusText = (status: string) => status === 'running' ? 'Ready' : status === 'error' ? 'Needs attention' : 'Starting';
const asTools = (items: unknown[]) => items as ToolItem[];

export function StdioServerList(props: Props) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-violet-400" />
          <h3 className="text-sm font-semibold text-slate-200">Active Stdio Servers</h3>
        </div>
        <button onClick={props.onRefresh} className="flex items-center gap-1 text-[11px] text-slate-500 transition hover:text-slate-300">
          <RefreshCw className={`h-3 w-3 ${props.loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>
      {!props.servers.length && !props.loading && <EmptyState />}
      <div className="space-y-3">{props.servers.map((server) => <ServerCard key={server.name} server={server} {...props} />)}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/40 p-8 text-center">
      <Terminal className="mx-auto h-8 w-8 text-slate-600" />
      <p className="mt-3 text-sm text-slate-500">No stdio MCP servers registered.</p>
      <p className="mt-1 text-xs text-slate-600">Add a server above to connect local tools.</p>
    </div>
  );
}

function ServerCard({ server, expanded, tools, executing, result, onToggle, onRemove, onRun }: Props & { server: StdioServer }) {
  const open = expanded === server.name;
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
      <div className="flex items-center justify-between p-4">
        <button onClick={() => onToggle(server.name)} className="flex flex-1 items-center gap-3 text-left">
          {open ? <ChevronDown className="h-4 w-4 text-slate-500" /> : <ChevronRight className="h-4 w-4 text-slate-500" />}
          <span className={`h-2 w-2 rounded-full ${statusColor(server.status)}`} />
          <span className="text-sm font-semibold text-slate-100">{server.name}</span>
          <span className="text-[10px] text-slate-500">({server.tool_count} tools)</span>
          <StatusPill status={server.status} />
        </button>
        <button onClick={() => onRemove(server.name)} className="rounded-lg border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-[11px] font-semibold text-red-400 transition hover:bg-red-500/20">Remove</button>
      </div>
      {open && <ServerDetail server={server} tools={asTools(tools[server.name] || [])} executing={executing} result={result} onRun={onRun} />}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const Icon = status === 'running' ? CheckCircle : status === 'error' ? AlertCircle : Clock;
  const color = status === 'running' ? 'text-emerald-300 bg-emerald-500/10' : status === 'error' ? 'text-red-300 bg-red-500/10' : 'text-amber-300 bg-amber-500/10';
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${color}`}><Icon className="h-3 w-3" />{statusText(status)}</span>;
}

function ServerDetail({ server, tools, executing, result, onRun }: { server: StdioServer; tools: ToolItem[]; executing: string | null; result: StdioResult | null; onRun: (serverName: string, toolName: string) => void }) {
  return (
    <div className="space-y-3 border-t border-slate-800 bg-slate-950/40 p-4">
      {server.command && <div className="text-[11px] text-slate-500">{server.command} {server.args?.join(' ')}</div>}
      {server.error_message && <div className="flex items-center gap-2 text-[11px] text-red-400"><AlertCircle className="h-3 w-3" />{server.error_message}</div>}
      {tools.map((tool) => <ToolRow key={tool.name} server={server.name} tool={tool} executing={executing} onRun={onRun} />)}
      {result?.id?.startsWith(`${server.name}:`) && <pre className={`max-h-48 overflow-auto rounded-lg p-3 text-[11px] ${result.status === 'error' ? 'bg-red-900/20 text-red-400' : 'bg-slate-900 text-slate-300'}`}>{JSON.stringify(result.data, null, 2)}</pre>}
    </div>
  );
}

function ToolRow({ server, tool, executing, onRun }: { server: string; tool: ToolItem; executing: string | null; onRun: (serverName: string, toolName: string) => void }) {
  const name = tool.name || 'tool';
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/60 p-2.5">
      <div>
        <span className="text-xs font-semibold text-slate-200">{name}</span>
        {tool.description && <span className="ml-2 text-[10px] text-slate-500">{tool.description.substring(0, 60)}</span>}
      </div>
      <button onClick={() => onRun(server, name)} disabled={executing === `${server}:${name}`} className="flex items-center gap-1 rounded bg-violet-600/30 px-2.5 py-1 text-[11px] text-violet-300 transition hover:bg-violet-600/50 disabled:opacity-50">
        <Play className="h-2.5 w-2.5" /> {executing === `${server}:${name}` ? 'Running...' : 'Run'}
      </button>
    </div>
  );
}
