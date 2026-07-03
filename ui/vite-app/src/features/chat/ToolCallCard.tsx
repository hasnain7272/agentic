import { useState } from 'react';
import type { ToolCall } from '@/features/chat/types';
import { Eye, CheckCircle2, XCircle, AlertCircle, Loader2, Clock } from 'lucide-react';

function tone(name: string) {
  if (name === 'delegate_task') return ['Sub-agent', 'bg-violet-400', 'text-violet-300', 'bg-violet-950/20 border-violet-800/30 ring-1 ring-violet-500/20', 'bg-violet-900/20'];
  if (name === 'search_past_decisions') return ['Memory', 'bg-amber-400', 'text-amber-300', 'bg-amber-950/20 border-amber-800/30 ring-1 ring-amber-500/20', 'bg-amber-900/20'];
  return ['Execution', 'bg-cyan-400', 'text-cyan-300', 'bg-slate-950/60 border-slate-700/50', 'bg-slate-800/70'];
}

function getStatusIcon(status?: string) {
  switch (status) {
    case 'done':
      return <CheckCircle2 className="h-3 w-3 text-emerald-400" />;
    case 'failed':
      return <XCircle className="h-3 w-3 text-red-400" />;
    case 'pending_approval':
      return <AlertCircle className="h-3 w-3 text-amber-400 animate-pulse" />;
    case 'running':
      return <Loader2 className="h-3 w-3 text-cyan-400 animate-spin" />;
    case 'pending':
      return <Clock className="h-3 w-3 text-slate-500" />;
    default:
      return <Clock className="h-3 w-3 text-slate-500" />;
  }
}

function formatDuration(started?: string, completed?: string) {
  if (!started) return null;
  const start = new Date(started).getTime();
  const end = completed ? new Date(completed).getTime() : Date.now();
  const diff = end - start;
  if (diff < 1000) return `${diff}ms`;
  if (diff < 60000) return `${(diff / 1000).toFixed(1)}s`;
  return `${Math.floor(diff / 60000)}m ${Math.floor((diff % 60000) / 1000)}s`;
}

export function ToolCallCard({ call }: { call: ToolCall }) {
  const [showResult, setShowResult] = useState(false);
  const name = call.function?.name || 'tool_execution';
  const argsRaw = call.function?.arguments || '{}';
  const [label, dot, title, shell, head] = tone(name);
  const status = call.status || 'pending';
  const duration = formatDuration(call.started_at, call.completed_at);

  return (
    <>
      <div className={`overflow-hidden rounded-lg border ${shell}`}>
        <div className={`flex items-center gap-2 border-b border-slate-700/50 px-3 py-2 ${head} relative overflow-hidden`}>
          {/* Progress indicator */}
          {call.progress !== undefined ? (
            <div className="flex items-center gap-1">
              <div className="h-2 w-2 rounded-full bg-cyan-400" />
              <span className="text-[9px] text-cyan-400">{call.progress}%</span>
            </div>
          ) : (
            <div className="flex items-center gap-1">
              <Loader2 className="h-3 w-3 text-cyan-400 animate-spin" />
              <span className="text-[9px] text-cyan-400">Running</span>
            </div>
          )}
          <span className="h-2 w-2 rounded-full ${dot} relative z-10" />
          <span className="font-mono text-xs font-semibold ${title} relative z-10">{name}</span>
          <span className="ml-1 flex items-center gap-1 relative z-10">
            {getStatusIcon(status)}
          </span>
          <span className="ml-auto flex items-center gap-1.5 text-[10px]">
            <span className="uppercase tracking-wider text-slate-500">{label}</span>
            {duration && <span className="text-slate-600 font-mono">{duration}</span>}
            {call.result !== undefined && (
              <button 
                onClick={() => setShowResult(!showResult)} 
                className="flex items-center gap-1 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-cyan-400 hover:bg-slate-700 transition"
              >
                <Eye className="h-3 w-3" /> {showResult ? 'Hide' : 'Show'} Result
              </button>
            )}
            {call.error && (
              <span className="text-red-400 font-medium">Failed</span>
            )}
          </span>
        </div>
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap px-3 py-2 font-mono text-xs text-slate-400">
          {argsRaw}
        </pre>
        {showResult && call.result !== undefined && (
          <div className="border-t border-slate-700/50 px-3 py-2 bg-slate-950/50">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Result</span>
              <button onClick={() => setShowResult(false)} className="text-[10px] text-slate-500 hover:text-slate-300">Close</button>
            </div>
            <pre className="max-h-60 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">
              {typeof call.result === 'string' ? call.result : JSON.stringify(call.result, null, 2)}
            </pre>
          </div>
        )}
        {call.error && (
          <div className="border-t border-red-900/30 px-3 py-2 bg-red-950/20">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-semibold text-red-400 uppercase tracking-wider">Error</span>
            </div>
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap font-mono text-xs text-red-300">
              {call.error}
            </pre>
          </div>
        )}
      </div>
    </>
  );
}
