export interface Folder {
  id: string;
  name: string;
  slug: string;
  color: string;
  description: string;
  permission: string;
}

export type FolderMode = 'list' | 'create' | 'import' | 'clone';

export const COLORS = [
  { id: 'cyan', bg: 'bg-cyan-500/20', ring: 'ring-cyan-500/50', text: 'text-cyan-400' },
  { id: 'violet', bg: 'bg-violet-500/20', ring: 'ring-violet-500/50', text: 'text-violet-400' },
  { id: 'amber', bg: 'bg-amber-500/20', ring: 'ring-amber-500/50', text: 'text-amber-400' },
  { id: 'emerald', bg: 'bg-emerald-500/20', ring: 'ring-emerald-500/50', text: 'text-emerald-400' },
  { id: 'rose', bg: 'bg-rose-500/20', ring: 'ring-rose-500/50', text: 'text-rose-400' },
  { id: 'sky', bg: 'bg-sky-500/20', ring: 'ring-sky-500/50', text: 'text-sky-400' },
];
