import { useState } from 'react';
import type { ToolCall } from '@/features/chat/types';
import { DiffViewer } from '@/features/workspace/DiffViewer';
import { Eye } from 'lucide-react';

function tone(name: string) {
  if (name === 'delegate_task') return ['Sub-agent', 'bg-violet-400', 'text-violet-300', 'bg-violet-950/20 border-violet-800/30 ring-1 ring-violet-500/20', 'bg-violet-900/20'];
  if (name === 'search_past_decisions') return ['Memory', 'bg-amber-400', 'text-amber-300', 'bg-amber-950/20 border-amber-800/30 ring-1 ring-amber-500/20', 'bg-amber-900/20'];
  return ['Execution', 'bg-cyan-400', 'text-cyan-300', 'bg-slate-950/60 border-slate-700/50', 'bg-slate-800/70'];
}

export function ToolCallCard({ call }: { call: ToolCall }) {
  const [showDiff, setShowDiff] = useState(false);
  const name = call.function?.name || 'tool_execution';
  const argsRaw = call.function?.arguments || '{}';
  const [label, dot, title, shell, head] = tone(name);

  const isFileEdit = name === 'replace_file_content' || name === 'multi_replace_file_content';
  let diffProps: any = null;

  if (isFileEdit) {
    try {
      const args = JSON.parse(argsRaw);
      if (args.TargetFile && (args.ReplacementContent || args.ReplacementChunks)) {
        diffProps = {
          path: args.TargetFile,
          content: args.ReplacementContent || JSON.stringify(args.ReplacementChunks, null, 2)
        };
      }
    } catch {}
  }

  return (
    <>
      <div className={`overflow-hidden rounded-lg border ${shell}`}>
        <div className={`flex items-center gap-2 border-b border-slate-700/50 px-3 py-2 ${head} relative overflow-hidden`}>
          {call.progress !== undefined && (
            <div className="absolute left-0 top-0 h-full bg-cyan-500/10 transition-all duration-300" style={{ width: `${call.progress}%` }} />
          )}
          <span className={`h-2 w-2 rounded-full ${dot} relative z-10`} />
          <span className={`font-mono text-xs font-semibold ${title} relative z-10`}>{name}</span>
          {call.progress !== undefined && (
            <span className="text-[9px] text-cyan-400 relative z-10">{call.progress}%</span>
          )}
          {diffProps && (
            <button onClick={() => setShowDiff(true)} className="ml-2 flex items-center gap-1 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-cyan-400 hover:bg-slate-700 transition">
              <Eye className="h-3 w-3" /> View Diff
            </button>
          )}
          <span className="ml-auto text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
        </div>
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap px-3 py-2 font-mono text-xs text-slate-400">
          {argsRaw}
        </pre>
      </div>
      {showDiff && diffProps && (
        <DiffViewer path={diffProps.path} content={diffProps.content} onClose={() => setShowDiff(false)} />
      )}
    </>
  );
}
