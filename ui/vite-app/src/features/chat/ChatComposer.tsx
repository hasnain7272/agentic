import { ChevronDown, Cpu, Loader2, Paperclip, Send, ShieldCheck } from 'lucide-react';
import type { ModelOption } from '@/features/chat/types';

interface Props {
  input: string;
  streaming: boolean;
  shadowMode: boolean;
  modelOptions: ModelOption[];
  activeModelId: string;
  inputRef: React.RefObject<HTMLTextAreaElement>;
  onInput: (value: string) => void;
  onSend: () => void;
  onUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onToggleShadow: () => void;
  onModelSelect: (id: string) => void;
}

export function ChatComposer({
  input,
  streaming,
  shadowMode,
  modelOptions,
  activeModelId,
  inputRef,
  onInput,
  onSend,
  onUpload,
  onToggleShadow,
  onModelSelect,
}: Props) {
  const submit = (event: React.FormEvent) => { event.preventDefault(); onSend(); };
  const keyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); onSend(); }
  };
  const activeModel = modelOptions.find((model) => model.id === activeModelId) || modelOptions[0];
  const nvidiaModels = modelOptions.filter((model) => model.provider === 'NVIDIA' || model.base_url?.includes('nvidia.com'));
  const otherModels = modelOptions.filter((model) => !nvidiaModels.includes(model));

  return (
    <form onSubmit={submit} className="rounded-3xl border border-slate-700/60 bg-slate-950/85 p-2 shadow-2xl shadow-black/20 ring-1 ring-slate-800/50 transition focus-within:border-cyan-500/50 focus-within:ring-cyan-500/20">
      <div className="flex items-center gap-2 border-b border-slate-800/60 px-2 pb-2">
        <div className="relative min-w-0 flex-1 sm:flex-none">
          <Cpu className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-cyan-300" />
          <select
            value={activeModel?.id || ''}
            onChange={(event) => onModelSelect(event.target.value)}
            disabled={streaming || modelOptions.length === 0}
            className="h-8 w-full appearance-none rounded-xl border border-slate-700/70 bg-slate-900 pl-8 pr-8 text-xs font-semibold text-slate-100 outline-none transition hover:border-cyan-500/40 disabled:opacity-50 sm:w-auto"
            title={activeModel?.model || 'No model configured'}
          >
            {modelOptions.length === 0 && <option value="">No model configured</option>}
            {nvidiaModels.length > 0 && (
              <optgroup label="NVIDIA">
                {nvidiaModels.map((model) => (
                  <option key={model.id} value={model.id}>{model.label}</option>
                ))}
              </optgroup>
            )}
            {otherModels.length > 0 && (
              <optgroup label="Other providers">
                {otherModels.map((model) => (
                  <option key={model.id} value={model.id}>{model.provider ? `${model.provider}: ${model.label}` : model.label}</option>
                ))}
              </optgroup>
            )}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
        </div>
        <div className="hidden min-w-0 flex-1 items-center gap-2 overflow-hidden text-[10px] text-slate-500 sm:flex">
          <span className="truncate font-mono">{activeModel?.model || 'Configure provider in settings'}</span>
          {activeModel?.provider === 'NVIDIA' && <span className="shrink-0 rounded-full bg-green-500/10 px-2 py-0.5 text-green-300">NVIDIA</span>}
          {activeModel?.base_url && <span className="shrink-0 rounded-full bg-cyan-500/10 px-2 py-0.5 text-cyan-300">OpenAI-compat</span>}
        </div>
        <button type="button" onClick={onToggleShadow} title="Shadow mode: simulate restricted actions" className={`flex h-8 shrink-0 items-center gap-1.5 rounded-xl px-2.5 text-[11px] font-semibold transition ${shadowMode ? 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/50' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'}`}>
          <ShieldCheck className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{shadowMode ? 'Shadow' : 'Live'}</span>
        </button>
      </div>
      <div className="flex items-end gap-2 px-2 pt-2">
        <textarea ref={inputRef} rows={1} value={input} onChange={(event) => onInput(event.target.value)} onKeyDown={keyDown} placeholder="Ask the agent to inspect, edit, or run..." disabled={streaming} className="max-h-[140px] min-h-10 flex-1 resize-none bg-transparent py-2 text-sm text-slate-100 outline-none placeholder:text-slate-500 disabled:opacity-50" />
        <label className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-xl text-slate-400 transition hover:bg-slate-800 hover:text-slate-200" title="Attach file">
          <input type="file" className="hidden" onChange={onUpload} />
          <Paperclip className="h-4 w-4" />
        </label>
        <button type="submit" disabled={streaming || !input.trim() || modelOptions.length === 0} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-cyan-600 text-white shadow-lg shadow-cyan-950/40 transition hover:bg-cyan-500 disabled:opacity-30">
          {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </form>
  );
}
