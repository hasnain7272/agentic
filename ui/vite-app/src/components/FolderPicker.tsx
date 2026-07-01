import { useCallback, useEffect, useRef, useState } from 'react';
import { Folder as FolderIcon, X } from 'lucide-react';
import { apiClient } from '@/api/client';
import { FolderForms } from './folder-picker/FolderForms';
import { FolderList } from './folder-picker/FolderList';
import { FolderModeTabs } from './folder-picker/FolderModeTabs';
import type { Folder, FolderMode } from './folder-picker/types';

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (folder: Folder) => void;
}

export function FolderPicker({ open, onClose, onSelect }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<FolderMode>('list');
  const [form, setForm] = useState({ name: '', path: '', branch: 'main', desc: '', color: 'cyan' });
  const update = (key: keyof typeof form, value: string) => setForm((prev) => ({ ...prev, [key]: value }));
  const reset = () => setForm({ name: '', path: '', branch: 'main', desc: '', color: 'cyan' });

  const loadFolders = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<{ folders: Folder[] }>('/folders/');
      setFolders(res.data?.folders || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open) {
      if (!dialog.open) dialog.showModal();
      loadFolders();
    } else if (dialog.open) {
      dialog.close();
      setMode('list');
    }
  }, [loadFolders, open]);

  const submit = async () => {
    if (!form.name.trim()) return;
    setLoading(true);
    try {
      if (mode === 'create') await apiClient.post('/folders/', { name: form.name.trim(), description: form.desc.trim(), color: form.color });
      if (mode === 'import') await apiClient.post('/folders/import-local', { name: form.name.trim(), local_path: form.path.trim(), color: form.color, description: 'Linked local directory' });
      if (mode === 'clone') await apiClient.post('/folders/clone', { name: form.name.trim(), repo_url: form.path.trim(), branch: form.branch, color: 'violet' });
      await loadFolders();
      setMode('list');
      reset();
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm('This will unlink or delete the project workspace. Proceed?')) return;
    await apiClient.delete(`/folders/${id}`);
    await loadFolders();
  };

  if (!open) return null;

  return (
    <dialog ref={dialogRef} onCancel={onClose} className="fixed inset-0 z-50 m-auto h-auto w-full max-w-md rounded-2xl border border-slate-700/60 bg-slate-900/95 p-0 text-slate-100 shadow-2xl shadow-black/60 backdrop:bg-black/70 backdrop:backdrop-blur-sm">
      <div className="flex flex-col">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/15 ring-1 ring-blue-500/30"><FolderIcon className="h-4 w-4 text-blue-400" /></div>
            <div><h2 className="text-sm font-semibold tracking-tight">Project Manager</h2><p className="text-[11px] text-slate-500">Initialize or switch your active project</p></div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-800 hover:text-slate-300"><X className="h-4 w-4" /></button>
        </div>
        <FolderModeTabs mode={mode} onMode={setMode} />
        {mode === 'list' ? (
          <FolderList folders={folders} loading={loading} onSelect={(folder) => { onSelect(folder); onClose(); }} onDelete={remove} />
        ) : (
          <FolderForms mode={mode} name={form.name} path={form.path} branch={form.branch} color={form.color} loading={loading} onName={(v) => update('name', v)} onPath={(v) => update('path', v)} onBranch={(v) => update('branch', v)} onColor={(v) => update('color', v)} onCancel={() => setMode('list')} onSubmit={submit} />
        )}
        <div className="flex items-center justify-between border-t border-slate-800 px-5 py-3">
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest text-slate-600">{folders.length.toString().padStart(2, '0')} // workspaces</p>
          <button onClick={onClose} className="rounded-lg text-xs text-slate-500 transition hover:text-slate-300">Close</button>
        </div>
      </div>
    </dialog>
  );
}
