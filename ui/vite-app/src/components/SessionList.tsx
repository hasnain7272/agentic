import { useState, useEffect } from 'react';
import { Loader2, Plus, Search, Settings, X, Zap, Check, Trash2, Clock } from 'lucide-react';
import { useSessions } from './session-drawer/useSessions';
import { EditableSessionName } from './session-drawer/EditableSessionName';
import { timeAgo } from './session-drawer/timeAgo';

interface SessionListProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenSettings: (sessionId: string) => void;
}

export function SessionList({ isOpen, onClose, onOpenSettings }: SessionListProps) {
  const sessions = useSessions(onClose, onOpenSettings);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);

  useEffect(() => {
    sessions.loadSessions();
  }, [sessions.loadSessions]);

  const handleDeleteConfirm = async (id: string, event: React.MouseEvent) => {
    event.stopPropagation();
    await sessions.endSession(id);
    setDeletingSessionId(null);
  };

  return (
    <div
      className={`
        fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-800/50 bg-[#0c0c0c]
        transition-transform duration-200
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800/50 px-3 py-2">
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest">Sessions</span>
        <button onClick={onClose} className="rounded p-1 text-slate-600 hover:bg-slate-800">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Search & New */}
      <div className="space-y-2 p-3 border-b border-slate-800/50">
        <button
          onClick={sessions.createSession}
          disabled={sessions.creating}
          className="flex w-full items-center justify-center gap-1.5 rounded bg-emerald-600/90 px-3 py-1.5 text-[11px] font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-50"
        >
          {sessions.creating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
          New Session
        </button>
        <div className="flex items-center gap-1.5 rounded border border-slate-800/60 bg-slate-900/50 px-2 py-1">
          <Search className="h-3 w-3 text-slate-600" />
          <input
            value={sessions.query}
            onChange={(e) => sessions.setQuery(e.target.value)}
            placeholder="Search..."
            className="min-w-0 flex-1 bg-transparent text-[11px] text-slate-300 outline-none placeholder:text-slate-700"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-0.5">
        {sessions.loading ? (
          <div className="flex items-center justify-center py-8 text-[11px] text-slate-600">
            <Loader2 className="mr-1.5 h-3 w-3 animate-spin" /> Loading...
          </div>
        ) : sessions.sessions.length > 0 ? (
          sessions.sessions.map((session) => {
            const active = session.id === sessions.currentSessionId;
            const isDeleting = deletingSessionId === session.id;

            return (
              <div
                key={session.id}
                onClick={() => !isDeleting && sessions.switchSession(session.id)}
                className={`group relative flex flex-col rounded-lg p-2.5 cursor-pointer transition-all ${
                  active ? 'bg-slate-800/60' : 'hover:bg-slate-800/30'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <EditableSessionName
                      sessionId={session.id}
                      name={session.name || session.id.slice(0, 8)}
                      onRename={sessions.loadSessions}
                    />
                    <div className="mt-0.5 flex items-center gap-1 text-[10px] text-slate-600">
                      {session.model ? (
                        <>
                          <Zap className="h-2 w-2 text-amber-500/70" />
                          <span className="truncate">{session.model.split('/').pop()}</span>
                        </>
                      ) : (
                        <span className="italic text-slate-700">No model</span>
                      )}
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    {isDeleting ? (
                      <div className="flex items-center gap-0.5 bg-slate-900/90 rounded-md p-0.5 border border-red-950">
                        <button onClick={(e) => handleDeleteConfirm(session.id, e)} className="rounded p-1 text-red-400 hover:bg-red-950/60">
                          <Check className="h-2.5 w-2.5" />
                        </button>
                        <button onClick={(e) => { e.stopPropagation(); setDeletingSessionId(null); }} className="rounded p-1 text-slate-500 hover:bg-slate-800">
                          <X className="h-2.5 w-2.5" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <button onClick={(e) => { e.stopPropagation(); onOpenSettings(session.id); }} className="rounded p-1 text-slate-600 hover:text-emerald-400 hover:bg-slate-800/60 transition-colors">
                          <Settings className="h-3.5 w-3.5" />
                        </button>
                        <button onClick={(e) => { e.stopPropagation(); setDeletingSessionId(session.id); }} className="rounded p-1 text-slate-600 hover:bg-red-950/40 hover:text-red-400 transition-colors">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="mt-1.5 flex items-center justify-between text-[9px] text-slate-700">
                  <div className="flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5 opacity-60" />
                    <span>{timeAgo(session.created_at)}</span>
                  </div>
                  {session.has_key && (
                    <span className="text-emerald-500/60 rounded px-1.5 py-0.5">
                      ●
                    </span>
                  )}
                </div>
              </div>
            );
          })
        ) : (
          <div className="px-5 py-12 text-center text-[11px] text-slate-600">
            No sessions found.
          </div>
        )}
      </div>
    </div>
  );
}