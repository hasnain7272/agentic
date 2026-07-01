import { FolderOpen, Loader2 } from 'lucide-react';
import { FolderItem } from './FolderItem';
import type { Folder } from './types';

interface Props {
  folders: Folder[];
  loading: boolean;
  onSelect: (folder: Folder) => void;
  onDelete: (id: string) => void;
}

export function FolderList({ folders, loading, onSelect, onDelete }: Props) {
  if (loading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-slate-500" /></div>;
  }
  if (!folders.length) {
    return <div className="py-12 text-center"><FolderOpen className="mx-auto h-10 w-10 text-slate-700" /><p className="mt-3 text-sm text-slate-500">No projects yet</p></div>;
  }
  return (
    <div className="max-h-72 overflow-y-auto">
      <div className="space-y-1 px-3 py-2">
        {folders.map((folder) => <FolderItem key={folder.id} folder={folder} onSelect={() => onSelect(folder)} onDelete={() => onDelete(folder.id)} />)}
      </div>
    </div>
  );
}
