import { Clock, Cpu, Settings, Trash2, Zap } from 'lucide-react';
import { EditableSessionName } from './EditableSessionName';
import { timeAgo } from './timeAgo';
import type { SessionInfo } from './types';

interface Props {
  session: SessionInfo;
  active: boolean;
  onRename: () => void;
  onSelect: () => void;
  onSettings: () => void;
  onEnd: () => void;
}

export function SessionRow({ session, active, onRename, onSelect, onSettings, onEnd }: Props) {
  return (
    <button onClick={onSelect} className={`group relative flex w-full items-start gap-3 rounded-xl px-3.5 py-3 text-left transition ${active ? 'bg-slate-800/80 ring-1 ring-cyan-500/30' : 'hover:bg-slate-800/40'}`}>
      {active && <div className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-cyan-500" />}
      <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${active ? 'bg-cyan-500/15 ring-1 ring-cyan-500/30' : 'bg-slate-800/60 ring-1 ring-slate-700/40'}`}>
        <Cpu className={`h-3.5 w-3.5 ${active ? 'text-cyan-400' : 'text-slate-500'}`} />
      </div>
      <div className="min-w-0 flex-1">
        <EditableSessionName sessionId={session.id} name={session.name || session.id.slice(0, 8)} onRename={onRename} />
        <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-slate-500">
          {session.model ? <><Zap className="h-2.5 w-2.5 text-amber-500" /><span className="truncate">{session.model.split('/').pop()}</span></> : <span className="italic text-slate-600">No provider</span>}
        </div>
        <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-600">
          <Clock className="h-2.5 w-2.5" />
          <span>{timeAgo(session.created_at)}</span>
          <span className={`rounded px-1 py-0.5 text-[9px] ${session.has_key ? 'bg-emerald-900/30 text-emerald-500' : 'bg-amber-900/30 text-amber-500'}`}>
            {session.has_key ? 'Key OK' : 'No Key'}
          </span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition group-hover:opacity-100">
        <IconButton title="Provider settings" onClick={onSettings}><Settings className="h-3.5 w-3.5" /></IconButton>
        <IconButton title="End session" danger onClick={onEnd}><Trash2 className="h-3.5 w-3.5" /></IconButton>
      </div>
    </button>
  );
}

function IconButton({ children, title, danger, onClick }: { children: React.ReactNode; title: string; danger?: boolean; onClick: () => void }) {
  return (
    <button onClick={(event) => { event.stopPropagation(); onClick(); }} title={title} className={`rounded-md p-1 text-slate-500 transition ${danger ? 'hover:bg-red-900/40 hover:text-red-400' : 'hover:bg-slate-700 hover:text-cyan-400'}`}>
      {children}
    </button>
  );
}
