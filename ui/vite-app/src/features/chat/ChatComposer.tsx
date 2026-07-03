import { Loader2, Send } from 'lucide-react';
import type { ModelOption } from '@/features/chat/types';

interface Props {
  input: string;
  streaming: boolean;
  modelOptions: ModelOption[];
  activeModelId: string;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  onInput: (value: string) => void;
  onSend?: () => void;
  onModelSelect: (id: string) => void;
  disabled?: boolean;
}

export function ChatComposer({
  input,
  streaming,
  modelOptions,
  activeModelId,
  inputRef,
  onInput,
  onSend,
  onModelSelect,
  disabled = false,
}: Props) {
  const submit = (e: React.FormEvent) => { e.preventDefault(); onSend?.(); };
  const keyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend?.(); }
  };
  const activeModel = modelOptions.find(m => m.id === activeModelId) || modelOptions[0];

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex items-center gap-2">
        <select
          value={activeModel?.id || ''}
          onChange={(e) => onModelSelect(e.target.value)}
          disabled={streaming || !modelOptions.length || disabled}
          className="flex-1 rounded bg-[#1e1e1e] border border-[#2e2e2e] px-3 py-1.5 text-[11px] font-medium text-slate-200 outline-none focus:border-emerald-500/50 disabled:opacity-50"
        >
          {!modelOptions.length && <option value="">No model configured</option>}
          {modelOptions.map((model) => (
            <option key={model.id} value={model.id}>{model.label}</option>
          ))}
        </select>
      </div>

      <div className="flex items-end gap-2">
        <textarea
          ref={inputRef}
          rows={1}
          value={input}
          onChange={(e) => onInput(e.target.value)}
          onKeyDown={keyDown}
          placeholder={disabled ? "Create a session first..." : "Message..."}
          disabled={streaming || disabled}
          className="flex-1 min-h-[42px] max-h-48 rounded bg-[#1e1e1e] border border-[#2e2e2e] px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-600 resize-none disabled:opacity-50 focus:border-emerald-500/50"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim() || !modelOptions.length || disabled}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-emerald-600 text-white transition hover:bg-emerald-500 disabled:opacity-30"
        >
          {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </form>
  );
}
