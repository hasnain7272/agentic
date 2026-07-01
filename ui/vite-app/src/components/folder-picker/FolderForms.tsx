import { GitBranch, Loader2 } from 'lucide-react';
import { COLORS, type FolderMode } from './types';

interface Props {
  mode: Exclude<FolderMode, 'list'>;
  name: string;
  path: string;
  branch: string;
  color: string;
  loading: boolean;
  onName: (value: string) => void;
  onPath: (value: string) => void;
  onBranch: (value: string) => void;
  onColor: (value: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
}

export function FolderForms(props: Props) {
  const action = props.mode === 'create' ? 'Create Workspace' : props.mode === 'import' ? 'Link Local Directory' : 'Clone Repository';
  const tone = props.mode === 'create' ? 'bg-violet-600 hover:bg-violet-500' : props.mode === 'import' ? 'bg-cyan-600 hover:bg-cyan-500' : 'bg-indigo-600 hover:bg-indigo-500';
  const disabled = props.loading || !props.name.trim() || (props.mode !== 'create' && !props.path.trim());

  return (
    <div className="space-y-4 px-5 py-6">
      <Field label={props.mode === 'create' ? 'Project Name' : 'Workspace Name'} value={props.name} onChange={props.onName} placeholder="e.g. Cinematic Studio" autoFocus />
      {props.mode !== 'create' && <Field label={props.mode === 'import' ? 'Absolute Host Path' : 'Repo URL'} value={props.path} onChange={props.onPath} placeholder={props.mode === 'import' ? 'D:\\Projects\\my-app' : 'https://github.com/...'} mono />}
      {props.mode === 'clone' && <Field label="Branch" value={props.branch} onChange={props.onBranch} placeholder="main" mono />}
      {props.mode === 'create' && <ColorPicker color={props.color} onColor={props.onColor} />}
      <div className="flex gap-2 pt-2">
        <button onClick={props.onCancel} className="flex-1 rounded-lg border border-slate-700 py-2 text-xs font-medium text-slate-400 transition hover:bg-slate-800">Cancel</button>
        <button onClick={props.onSubmit} disabled={disabled} className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-bold text-white shadow-lg transition disabled:opacity-50 ${tone}`}>
          {props.loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : props.mode === 'clone' ? <GitBranch className="h-3.5 w-3.5" /> : null}
          {props.loading && props.mode === 'clone' ? 'Cloning...' : action}
        </button>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, mono, autoFocus }: { label: string; value: string; onChange: (value: string) => void; placeholder: string; mono?: boolean; autoFocus?: boolean }) {
  return (
    <div>
      <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</label>
      <input value={value} onChange={(event) => onChange(event.target.value)} autoFocus={autoFocus} placeholder={placeholder} className={`w-full rounded-lg border border-slate-700/60 bg-slate-800/50 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-600/60 focus:ring-1 focus:ring-cyan-600/30 ${mono ? 'font-mono' : ''}`} />
    </div>
  );
}

function ColorPicker({ color, onColor }: { color: string; onColor: (value: string) => void }) {
  return (
    <div className="flex justify-center gap-2">
      {COLORS.map((item) => <button key={item.id} onClick={() => onColor(item.id)} className={`h-7 w-7 rounded-full ${item.bg} transition-all ${color === item.id ? `${item.ring} scale-110 ring-2` : 'opacity-40 hover:opacity-100'}`} />)}
    </div>
  );
}
