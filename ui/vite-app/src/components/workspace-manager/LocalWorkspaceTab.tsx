import { IconCheck, IconPlus } from '@/features/workspace/WorkspaceIcons';

interface Props {
  loading: boolean;
  onUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

export function LocalWorkspaceTab({ loading, onUpload }: Props) {
  return (
    <div className="wm-form">
      <div
        className="group flex cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed border-slate-800 bg-slate-900/20 p-10 transition-all hover:border-blue-500/30 hover:bg-slate-900/40"
        onClick={() => document.getElementById('sandbox-upload-input')?.click()}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-500/10 text-blue-400 transition-transform group-hover:scale-110">
          {loading ? <span className="wm-spinner" /> : <IconPlus />}
        </div>
        <div className="text-center">
          <p className="text-sm font-bold text-slate-200">Upload Project Files</p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-slate-500">Click to browse folders or files</p>
        </div>
        <input id="sandbox-upload-input" type="file" multiple className="hidden" onChange={onUpload} />
      </div>
      <div className="mt-6 flex items-center gap-3 rounded-xl border border-blue-500/10 bg-blue-500/5 p-3">
        <div className="rounded-lg bg-blue-500/10 p-2 text-blue-400"><IconCheck /></div>
        <div>
          <p className="text-xs font-bold text-blue-300">Isolated Environment</p>
          <p className="text-[10px] leading-relaxed text-blue-500/70">Files are uploaded to a session-isolated sandbox.</p>
        </div>
      </div>
    </div>
  );
}
