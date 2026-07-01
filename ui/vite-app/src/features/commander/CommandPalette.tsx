import { useEffect, useRef, useState } from 'react';
import { FolderOpen, TerminalSquare, Zap } from 'lucide-react';
import { apiClient } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { useSessionStore } from '@/store/sessionStore';
import { useTaskStore } from '@/store/taskStore';

interface Folder { id: string; name: string; slug: string; color: string; }

function ActionButton({
  icon,
  label,
  hint,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  hint: string;
  onClick: (e: React.MouseEvent) => void;
}) {
  return (
    <button className="flex w-full items-center gap-3 px-4 py-2 text-left transition hover:bg-slate-800/60" onClick={onClick}>
      {icon}
      <span className="flex-1 text-sm text-slate-300">{label}</span>
      <span className="text-xs text-slate-600">{hint}</span>
    </button>
  );
}

export function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [sending, setSending] = useState(false);
  const [folders, setFolders] = useState<Folder[]>([]);
  const sessionId = useSessionStore((s) => s.sessionId);
  const mountedFolders = useSessionStore((s) => s.mountedFolders);
  const ensureSession = useSessionStore((s) => s.ensureSession);
  const upsertTask = useTaskStore((s) => s.upsertTask);
  const setActiveTask = useTaskStore((s) => s.setActiveTask);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setIsOpen((open) => !open);
      }
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    apiClient.get<{ folders: Folder[] }>('/folders/').then((res) => {
      if (res.data?.folders) setFolders(res.data.folders);
    });
  }, [isOpen]);

  const handleSelectFolder = async (folder: Folder) => {
    await ensureSession([folder.slug]);
    setIsOpen(false);
    setQuery('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || sending) return;
    setSending(true);
    const res = await apiClient.post<{ task_id: string }>('/tasks/', { session_id: sessionId, description: query.trim() });
    if (res.data?.task_id) {
      upsertTask({ id: res.data.task_id, description: query, status: 'pending' });
      setActiveTask(res.data.task_id);
    }
    setSending(false);
    setIsOpen(false);
    setQuery('');
  };

  const prime = (value: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    setQuery(value);
    inputRef.current?.focus();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 px-3 pt-[12vh] backdrop-blur-sm fade-in sm:pt-[15vh]" onClick={() => setIsOpen(false)}>
      <div className="w-full max-w-2xl overflow-hidden rounded-xl border border-slate-800 bg-slate-950 shadow-2xl scale-in" onClick={(e) => e.stopPropagation()}>
        <form onSubmit={handleSubmit} className="flex items-center border-b border-slate-800 px-4">
          <TerminalSquare className="mr-3 h-5 w-5 text-slate-500" />
          <input
            ref={inputRef}
            autoFocus
            className="h-14 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-slate-500"
            placeholder="Ask the agent or switch projects..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={sending}
          />
          <Badge variant="outline" className={sending ? 'animate-pulse' : ''}>{sending ? '...' : 'Enter'}</Badge>
        </form>

        {folders.length > 0 && (
          <div className="border-b border-slate-800/60">
            <div className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">Recent Projects</div>
            <div className="max-h-40 overflow-y-auto pb-2">
              {folders.slice(0, 5).map((folder) => (
                <button key={folder.id} onClick={() => handleSelectFolder(folder)} className={`flex w-full items-center gap-3 px-4 py-2 text-left transition hover:bg-slate-800/60 ${mountedFolders.includes(folder.slug) ? 'bg-slate-800/60' : ''}`}>
                  <FolderOpen className="h-4 w-4 text-violet-400" />
                  <span className="flex-1 truncate text-sm text-slate-300">{folder.name}</span>
                  <span className="text-xs text-slate-600">{folder.slug.split('-').slice(0, 2).join('-')}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="border-b border-slate-800/60">
          <div className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">Quick Actions</div>
          <div className="pb-2">
            <ActionButton icon={<span className="flex h-5 w-5 items-center justify-center rounded bg-cyan-900/40 text-cyan-400">?</span>} label="Global Search" hint="Type /search" onClick={prime('/search ')} />
            <ActionButton icon={<Zap className="h-4 w-4 text-emerald-400" />} label="Tool Registry" hint="Type /tools" onClick={prime('/tools ')} />
          </div>
        </div>

        <div className="flex items-center justify-between px-4 py-2.5 text-xs text-slate-600">
          <div className="flex gap-3 max-sm:hidden">
            <span><kbd className="rounded bg-slate-800 px-1.5 py-0.5 font-mono">Ctrl K</kbd> Command</span>
            <span><kbd className="rounded bg-slate-800 px-1.5 py-0.5 font-mono">Esc</kbd> Close</span>
          </div>
          <span className="flex items-center gap-1 text-slate-500"><Zap className="h-3 w-3" /> AI-powered</span>
        </div>
      </div>
    </div>
  );
}
