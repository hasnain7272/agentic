import { useState } from 'react';
import { Loader2, Plus, Wand2 } from 'lucide-react';

interface Props {
  onRegister: (form: { name: string; command: string; args: string; working_dir: string }) => Promise<void>;
  onError: (message: string) => void;
}

export function StdioRegisterCard({ onRegister, onError }: Props) {
  const [form, setForm] = useState({ name: '', command: 'python', args: '', working_dir: '' });
  const [saving, setSaving] = useState(false);
  
  const update = (key: keyof typeof form, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async () => {
    if (!form.name || !form.command) return;
    setSaving(true);
    try {
      await onRegister(form);
      setForm({ name: '', command: 'python', args: '', working_dir: '' });
    } catch (error) {
      onError(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-2xl border border-dashed border-violet-700/50 bg-violet-900/10 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Plus className="h-4 w-4 text-violet-400" />
        <h3 className="text-sm font-semibold text-slate-200">Add Stdio MCP Server</h3>
      </div>
      
      <div className="mb-3 flex flex-wrap gap-2">
        <Preset label="Blender MCP" onClick={() => setForm({ 
            name: 'Blender', 
            command: 'python', 
            args: '-m blender_mcp_server.server', 
            working_dir: 'd:\\AI_Content_Studio\\ai_blender_cinematic\\antigravity\\blender-mcp-server\\src' 
        })} />
        <Preset label="Filesystem" onClick={() => setForm({ 
            name: 'filesystem', 
            command: 'npx', 
            args: '-y @modelcontextprotocol/server-filesystem .', 
            working_dir: '' 
        })} />
      </div>

      <div className="grid gap-2 grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
        <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold ml-1">Server Name</label>
            <input value={form.name} onChange={(e) => update('name', e.target.value)} placeholder="e.g. Blender" className="rounded-lg border border-slate-700/60 bg-slate-900/50 px-3 py-2 text-xs text-slate-100 outline-none transition focus:border-violet-500/40" />
        </div>
        <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold ml-1">Command</label>
            <input value={form.command} onChange={(e) => update('command', e.target.value)} placeholder="e.g. python" className="rounded-lg border border-slate-700/60 bg-slate-900/50 px-3 py-2 text-xs text-slate-100 outline-none transition focus:border-violet-500/40" />
        </div>
        <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold ml-1">Arguments</label>
            <input value={form.args} onChange={(e) => update('args', e.target.value)} placeholder="-m blender_mcp_server.server" className="rounded-lg border border-slate-700/60 bg-slate-900/50 px-3 py-2 text-xs text-slate-100 outline-none transition focus:border-violet-500/40" />
        </div>
        <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold ml-1">Working Directory</label>
            <input value={form.working_dir} onChange={(e) => update('working_dir', e.target.value)} placeholder="/path/to/src" className="rounded-lg border border-slate-700/60 bg-slate-900/50 px-3 py-2 text-xs text-slate-100 outline-none transition focus:border-violet-500/40" />
        </div>
      </div>
      
      <button onClick={submit} disabled={saving || !form.name || !form.command} className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-lg bg-violet-600 px-3 py-2.5 text-xs font-bold text-white transition hover:bg-violet-500 disabled:opacity-50">
        {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
        Register Stdio Server
      </button>
    </div>
  );
}

function Preset({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-900/70 px-2.5 py-1 text-[11px] font-semibold text-slate-400 transition hover:border-violet-600/50 hover:text-violet-300">
      <Wand2 className="h-3 w-3" />{label}
    </button>
  );
}
