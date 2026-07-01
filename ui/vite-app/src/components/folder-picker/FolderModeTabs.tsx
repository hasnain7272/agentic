import { FolderInput, GitBranch, Plus } from 'lucide-react';
import type { FolderMode } from './types';

interface Props {
  mode: FolderMode;
  onMode: (mode: FolderMode) => void;
}

export function FolderModeTabs({ mode, onMode }: Props) {
  return (
    <div className="flex gap-1.5 border-b border-slate-800/60 bg-slate-800/10 p-3">
      <Tab active={mode === 'create'} tone="bg-indigo-600" label="Cloud" onClick={() => onMode('create')}><Plus className="h-3 w-3" /></Tab>
      <Tab active={mode === 'import'} tone="bg-blue-600" label="Local" onClick={() => onMode('import')}><FolderInput className="h-3 w-3" /></Tab>
      <Tab active={mode === 'clone'} tone="bg-slate-700" label="Git" onClick={() => onMode('clone')}><GitBranch className="h-3 w-3" /></Tab>
    </div>
  );
}

function Tab({ active, tone, label, onClick, children }: { active: boolean; tone: string; label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`flex flex-1 items-center justify-center gap-1 rounded-md py-1.5 text-[10px] font-bold uppercase tracking-wider transition ${active ? `${tone} text-white` : 'bg-slate-800 text-slate-400 hover:text-slate-200'}`}>
      {children}{label}
    </button>
  );
}
