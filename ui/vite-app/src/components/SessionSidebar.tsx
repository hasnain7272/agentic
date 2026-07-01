import { useEffect, useState } from 'react';
import { Loader2, Plus, Search, Radio, Settings, Trash2, Zap, Clock, Check, X } from 'lucide-react';
import { useSessions } from './session-drawer/useSessions';
import { EditableSessionName } from './session-drawer/EditableSessionName';
import { timeAgo } from './session-drawer/timeAgo';

interface SessionSidebarProps {
  onOpenSettings: (sessionId: string) => void;
}

export function SessionSidebar({ onOpenSettings }: SessionSidebarProps) {
  const sessions = useSessions(() => {}, onOpenSettings);
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
    <div className="flex h-full flex-col bg-slate-950/40 text-slate-200">
      {/* Search & Actions */}
      <div className="space-y-3 p-4 border-b border-slate-800/50 bg-slate-900/10">
        <button
          onClick={sessions.createSession}
          disabled={sessions.creating}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-cyan-950/40 transition-all hover:from-cyan-500 hover:to-blue-500 hover:shadow-cyan-900/30 disabled:opacity-50 active:scale-[0.98]"
        >
          {sessions.creating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plus className="h-3.5 w-3.5" />
          )}
          New Session
        </button>
        <label className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/30 px-3 py-2 text-slate-500 focus-within:border-slate-700/80 transition-colors">
          <Search className="h-3.5 w-3.5" />
          <input
            value={sessions.query}
            onChange={(event) => sessions.setQuery(event.target.value)}
            placeholder="Search sessions..."
            className="min-w-0 flex-1 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-600"
          />
        </label>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
        {sessions.loading ? (
          <div className="flex items-center justify-center py-12 text-xs text-slate-500">
            <Loader2 className="mr-2 h-4 w-4 animate-spin text-cyan-500" />
            Loading sessions...
          </div>
        ) : sessions.sessions.length > 0 ? (
          sessions.sessions.map((session) => {
            const active = session.id === sessions.currentSessionId;
            const isDeleting = deletingSessionId === session.id;

            return (
              <div
                key={session.id}
                onClick={() => !isDeleting && sessions.switchSession(session.id)}
                className={`group relative flex w-full flex-col rounded-xl p-3 text-left transition-all duration-200 border cursor-pointer ${
                  active
                    ? 'bg-slate-800/50 border-cyan-500/30 ring-1 ring-cyan-500/20'
                    : 'bg-transparent border-transparent hover:bg-slate-800/20 hover:border-slate-800/40'
                }`}
              >
                {active && (
                  <div className="absolute left-0 top-3 bottom-3 w-1 rounded-r-full bg-cyan-500" />
                )}

                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <EditableSessionName
                      sessionId={session.id}
                      name={session.name || session.id.slice(0, 8)}
                      onRename={sessions.loadSessions}
                    />
                    
                    <div className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-400">
                      {session.model ? (
                        <>
                          <Zap className="h-2.5 w-2.5 text-amber-500" />
                          <span className="truncate">{session.model.split('/').pop()}</span>
                        </>
                      ) : (
                        <span className="italic text-slate-600">No model configured</span>
                      )}
                    </div>
                  </div>

                  {/* Actions & Confirmations */}
                  <div className="flex shrink-0 items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    {isDeleting ? (
                      <div className="flex items-center gap-1 bg-slate-900/90 rounded-lg p-0.5 border border-red-950">
                        <button
                          title="Confirm Delete"
                          onClick={(e) => handleDeleteConfirm(session.id, e)}
                          className="rounded p-1 text-red-400 hover:bg-red-950/60"
                        >
                          <Check className="h-3 w-3" />
                        </button>
                        <button
                          title="Cancel"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeletingSessionId(null);
                          }}
                          className="rounded p-1 text-slate-400 hover:bg-slate-800"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <button
                          title="Provider Settings"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenSettings(session.id);
                          }}
                          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-cyan-400 transition-colors"
                        >
                          <Settings className="h-3.5 w-3.5" />
                        </button>
                        <button
                          title="Delete Session"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeletingSessionId(session.id);
                          }}
                          className="rounded-lg p-1.5 text-slate-400 hover:bg-red-950/40 hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500">
                  <div className="flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5 opacity-60" />
                    <span>{timeAgo(session.created_at)}</span>
                  </div>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[9px] font-medium ${
                      session.has_key
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    }`}
                  >
                    {session.has_key ? 'API Key Active' : 'No Key'}
                  </span>
                </div>
              </div>
            );
          })
        ) : (
          <div className="px-5 py-12 text-center text-xs text-slate-600">
            No sessions found.
          </div>
        )}
      </div>

      <div className="border-t border-slate-900 bg-slate-950/80 p-3.5">
        <p className="text-[10px] text-slate-500 leading-relaxed">
          Each session isolates environment variables, files, and chat history.
        </p>
      </div>
    </div>
  );
}
