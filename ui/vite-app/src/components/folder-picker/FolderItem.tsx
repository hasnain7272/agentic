import { Folder as FolderIcon, FolderOpen, Trash2 } from 'lucide-react';
import { COLORS, type Folder } from './types';

interface Props {
  folder: Folder;
  onSelect: () => void;
  onDelete: () => void;
}

export function FolderItem({ folder, onSelect, onDelete }: Props) {
  const color = COLORS.find((item) => item.id === folder.color) || COLORS[0];
  return (
    <div className={`group flex items-center gap-3 rounded-lg p-3 transition hover:bg-slate-800/60 ${color.bg}`}>
      <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${color.bg} ${color.ring} ring-1`}>
        <FolderIcon className={`h-5 w-5 ${color.text}`} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-slate-200">{folder.name}</span>
          {folder.permission !== 'viewer' && <span className="rounded bg-slate-800/80 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">{folder.permission}</span>}
        </div>
        {folder.description && <p className="mt-0.5 truncate text-xs text-slate-500">{folder.description}</p>}
      </div>
      <div className="flex items-center gap-1 opacity-0 transition group-hover:opacity-100">
        {folder.permission === 'owner' && <button onClick={onDelete} className="rounded p-1.5 text-slate-500 hover:bg-red-900/30 hover:text-red-400"><Trash2 className="h-3.5 w-3.5" /></button>}
        <button onClick={onSelect} className="rounded p-1.5 text-slate-500 hover:bg-slate-700 hover:text-slate-300"><FolderOpen className="h-3.5 w-3.5" /></button>
      </div>
    </div>
  );
}
