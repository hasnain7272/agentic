import { ChevronDown, Loader2, Paperclip, Send } from 'lucide-react';
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
  const submit = (e: React.FormEvent) => { e.preventDefault(); onSend(); };
  const keyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); }
  };
  const activeModel = modelOptions.find(m => m.id === activeModelId) || modelOptions[0];

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex items-center gap-2">
        <select
          value={activeModel?.id || ''}
          onChange={(e) => onModelSelect(e.target.value)}
          disabled={streaming || !modelOptions.length}
          className="flex-1 rounded bg-[#1e1e1e] border border-[#2e2e2e] px-3 py-1.5 text-[11px] font-medium text-slate-200 outline-none focus:border-emerald-500/50 disabled:opacity-50"
        >
          {!modelOptions.length && <option value="">No model configured</option>}
          {modelOptions.map((model) => (
            <option key={model.id} value={model.id}>{model.label}</option>
          ))}
        </select>
        
        <button
          type="button"
          onClick={onToggleShadow}
          className={`rounded px-2 py-1.5 text-[10px] font-medium transition ${shadowMode
            ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
            : 'bg-[#1e1e1e] text-slate-500 border border-[#2e2e2e] hover:text-slate-300'
          }`}
        >
          {shadowMode ? 'Shadow' : 'Live'}
        </button>
      </div>

      <div className="flex items-end gap-2">
        <textarea
          ref={inputRef}
          rows={1}
          value={input}
          onChange={(e) => onInput(e.target.value)}
          onKeyDown={keyDown}
          placeholder="Message..."
          disabled={streaming}
          className="flex-1 min-h-[42px] max-h-48 rounded bg-[#1e1e1e] border border-[#2e2e2e] px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-600 resize-none disabled:opacity-50 focus:border-emerald-500/50"
        />
        <label className="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded bg-[#1e1e1e] border border-[#2e2e2e] text-slate-500 hover:border-emerald-500/50 hover:text-slate-300 transition" title="Attach file">
          <input type="file" className="hidden" onChange={onUpload} />
          <Paperclip className="h-4 w-4" />
        </label>
        <button
          type="submit"
          disabled={streaming || !input.trim() || !modelOptions.length}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-emerald-600 text-white transition hover:bg-emerald-500 disabled:opacity-30"
        >
          {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </form>
  );
}