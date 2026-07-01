import { useEffect } from 'react';
import { Loader2, Plus, Radio, Search, X } from 'lucide-react';
import { SessionRow } from './session-drawer/SessionRow';
import { useSessions } from './session-drawer/useSessions';

interface SessionDrawerProps {
  open: boolean;
  onClose: () => void;
  onOpenSettings: (sessionId: string) => void;
}

export function SessionDrawer({ open, onClose, onOpenSettings }: SessionDrawerProps) {
  const sessions = useSessions(onClose, onOpenSettings);

  useEffect(() => {
    if (open) sessions.loadSessions();
  }, [open, sessions.loadSessions]);

  return (
    <>
      {open && <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" onClick={onClose} />}
      <div className={`fixed left-0 top-0 z-50 flex h-full w-80 flex-col border-r border-slate-800/80 bg-slate-950/98 shadow-2xl shadow-black/40 transition-transform duration-300 ease-out ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/15 ring-1 ring-emerald-500/30">
              <Radio className="h-3.5 w-3.5 text-emerald-400" />
            </div>
            <h2 className="text-sm font-semibold text-slate-200">Sessions</h2>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-800 hover:text-slate-300"><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-3 border-b border-slate-800/60 p-3">
          <button onClick={sessions.createSession} disabled={sessions.creating} className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-cyan-900/30 transition hover:bg-cyan-500 disabled:opacity-50">
            {sessions.creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
            New Session
          </button>
          <label className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-slate-500">
            <Search className="h-3.5 w-3.5" />
            <input value={sessions.query} onChange={(event) => sessions.setQuery(event.target.value)} placeholder="Search sessions" className="min-w-0 flex-1 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-600" />
          </label>
        </div>
        <div className="flex-1 overflow-y-auto">
          {sessions.loading ? <Loading /> : sessions.sessions.length ? (
            <div className="space-y-1 p-2">
              {sessions.sessions.map((session) => (
                <SessionRow
                  key={session.id}
                  session={session}
                  active={session.id === sessions.currentSessionId}
                  onRename={sessions.loadSessions}
                  onSelect={() => sessions.switchSession(session.id)}
                  onSettings={() => onOpenSettings(session.id)}
                  onEnd={() => sessions.endSession(session.id)}
                />
              ))}
            </div>
          ) : <Empty />}
        </div>
        <div className="border-t border-slate-800/60 px-5 py-3">
          <p className="text-[10px] text-slate-600">Each session keeps its own provider, credentials, and conversation history.</p>
        </div>
      </div>
    </>
  );
}

function Loading() {
  return <div className="flex items-center justify-center py-12 text-xs text-slate-600"><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading...</div>;
}

function Empty() {
  return <div className="px-5 py-12 text-center text-xs text-slate-600">No sessions found.</div>;
}
