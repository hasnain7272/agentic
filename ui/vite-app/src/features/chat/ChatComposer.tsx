import { Loader2, Send, Square } from 'lucide-react';
import type { ModelOption } from '@/features/chat/types';

interface Props {
  input: string;
  streaming: boolean;
  modelOptions: ModelOption[];
  modelPriorities: string[];
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  onInput: (value: string) => void;
  onSend?: () => void;
  onStop?: () => void;
  onModelPrioritiesChange?: (priorities: string[]) => void;
  disabled?: boolean;
}

export function ChatComposer({
  input,
  streaming,
  modelOptions,
  modelPriorities = [],
  inputRef,
  onInput,
  onSend,
  onStop,
  onModelPrioritiesChange,
  disabled = false,
}: Props) {
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (streaming) return;
    onSend?.();
  };
  const keyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (streaming) return;
      onSend?.();
    }
  };

  const removeModel = (id: string) => {
    if (onModelPrioritiesChange) {
      onModelPrioritiesChange(modelPriorities.filter(m => m !== id));
    }
  };

  const addModel = (id: string) => {
    if (id && onModelPrioritiesChange && !modelPriorities.includes(id)) {
      onModelPrioritiesChange([...modelPriorities, id]);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      {/* Dynamic Swarm Team Configurator */}
      <div className="rounded-lg border border-slate-800 bg-[#0e0e0e]/50 p-2.5 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold px-0.5">Active Swarm Model Team</span>
          <select
            value=""
            onChange={(e) => { addModel(e.target.value); e.target.value = ""; }}
            disabled={streaming || disabled}
            className="rounded bg-[#1a1a1a] border border-[#2e2e2e] px-2 py-1 text-[10px] font-medium text-cyan-400 outline-none hover:border-cyan-500/50 cursor-pointer"
          >
            <option value="">+ Add Model to Swarm</option>
            {modelOptions.filter(m => !modelPriorities.includes(m.id)).map((model) => (
              <option key={model.id} value={model.id}>{model.label}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 min-h-[32px]">
          {!modelPriorities || !modelPriorities.length ? (
            <span className="text-xs text-slate-600 italic px-0.5">No swarm models configured. Add a model to start.</span>
          ) : (
            modelPriorities.map((modelId, index) => {
              const matched = modelOptions.find(m => m.id === modelId);
              const label = matched ? matched.label : modelId;
              const isLead = index === 0;
              return (
                <div 
                  key={modelId} 
                  className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs border ${
                    isLead 
                      ? 'bg-emerald-950/20 border-emerald-800/40 text-emerald-400 font-semibold' 
                      : 'bg-slate-900/30 border-slate-800/80 text-slate-400'
                  }`}
                >
                  <span className="text-[9px] uppercase tracking-wider text-slate-500">{index + 1} {isLead ? 'Lead' : 'QA'}</span>
                  <span>{label}</span>
                  <button
                    type="button"
                    onClick={() => removeModel(modelId)}
                    disabled={streaming || disabled}
                    className="hover:text-red-400 text-slate-600 transition ml-1"
                  >
                    ×
                  </button>
                </div>
              );
            })
          )}
        </div>
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
          type={streaming ? 'button' : 'submit'}
          onClick={streaming ? onStop : undefined}
          disabled={!streaming && (!input.trim() || !modelOptions.length || disabled)}
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded transition ${
            streaming 
              ? 'bg-rose-600 hover:bg-rose-500 text-white cursor-pointer' 
              : 'bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-30'
          }`}
        >
          {streaming ? <Square className="h-3.5 w-3.5 fill-white" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </form>
  );
}
