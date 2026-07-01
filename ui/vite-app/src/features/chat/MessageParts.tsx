import { Brain, ChevronDown, ChevronRight, GitBranch, Wrench } from 'lucide-react';
import { useState } from 'react';
import { apiClient } from '@/api/client';
import { useSessionStore } from '@/store/sessionStore';

export function StreamingDots() {
  return (
    <span className="ml-1 inline-flex items-center">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="mr-0.5 inline-block h-2 w-2 animate-pulse rounded-full bg-cyan-400 last:mr-0"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}

export function ReasoningBlock({ text, streaming }: { text: string; streaming?: boolean }) {
  const [open, setOpen] = useState(streaming || false);
  if (!text) return null;
  return (
    <div className="mb-2 rounded-lg border border-violet-800/30 bg-violet-950/20">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1.5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-violet-400/80 transition hover:text-violet-300"
      >
        <Brain className="h-3 w-3" />
        Reasoning
        {streaming && <span className="ml-1 h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" />}
        {open ? <ChevronDown className="ml-auto h-3 w-3" /> : <ChevronRight className="ml-auto h-3 w-3" />}
      </button>
      {open && (
        <div className="whitespace-pre-wrap border-t border-violet-800/20 px-3 py-2 text-xs leading-relaxed text-violet-300/70">
          {text}
        </div>
      )}
    </div>
  );
}

export function ApprovalBlock({
  id,
  toolName,
  onApprove,
}: {
  id: string;
  toolName?: string;
  onApprove: (id: string, decision: 'approved' | 'denied') => void;
}) {
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl bg-slate-900/40 p-3 ring-1 ring-amber-500/30">
      <div className="flex items-center gap-2 text-xs font-medium text-amber-300">
        <Wrench className="h-3 w-3" />
        <span>Permission Required: {toolName}</span>
      </div>
      <div className="flex gap-2">
        {(['approved', 'denied'] as const).map((decision) => (
          <button
            key={decision}
            onClick={() => onApprove(id, decision)}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-semibold transition active:scale-95 ${
              decision === 'approved'
                ? 'bg-cyan-600 text-white hover:bg-cyan-500'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            {decision === 'approved' ? 'Approve' : 'Deny'}
          </button>
        ))}
      </div>
    </div>
  );
}

export function StatusMark({ status }: { status?: string }) {
  if (status !== 'APPROVED' && status !== 'DENIED') return null;
  const denied = status === 'DENIED';
  return (
    <div className={`mt-2 flex items-center gap-1.5 text-[10px] font-medium opacity-80 ${denied ? 'text-rose-400' : 'text-cyan-400'}`}>
      <div className={`h-1 w-1 rounded-full ${denied ? 'bg-rose-400' : 'bg-cyan-400'}`} />
      {denied ? 'Denied' : 'Approved'}
    </div>
  );
}

export function BranchButton({ id, role, sessionId }: { id?: string; role: string; sessionId?: string }) {
  const setSessionId = useSessionStore((s) => s.setSessionId);
  const fork = async () => {
    if (!id || !sessionId) return;
    const res = await apiClient.post<{ id: string }>(`/sessions/${sessionId}/fork`, { message_id: id });
    if (!res.data?.id) throw new Error(res.error || 'Fork failed');
    setSessionId(res.data.id);
    window.location.reload();
  };

  return (
    <div className={`absolute top-0 opacity-0 transition group-hover:opacity-100 max-sm:hidden ${role === 'user' ? '-left-8' : '-right-8'}`}>
      <button onClick={() => fork().catch(() => console.error('Fork failed'))} className="rounded-full bg-slate-800 p-1.5 text-slate-400 shadow-lg hover:bg-slate-700 hover:text-cyan-400" title="Branch from here">
        <GitBranch className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
