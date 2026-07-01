import { useEffect, useRef } from 'react';
import { CheckCircle2, CircleDashed, ShieldAlert, Sparkles, Wrench } from 'lucide-react';
import { ChatComposer } from '@/features/chat/ChatComposer';
import { MessageBubble } from '@/features/chat/MessageBubble';
import { useChatController } from '@/features/chat/useChatController';
import type { ChatActivity } from '@/features/chat/types';

export function ChatPane() {
  const endRef = useRef<HTMLDivElement>(null);
  const chat = useChatController();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat.msgs]);

  useEffect(() => {
    const insert = (event: Event) => {
      const detail = (event as CustomEvent<{ text?: string }>).detail;
      if (!detail?.text) return;
      chat.setInput(chat.input ? `${chat.input}\n${detail.text}` : detail.text);
      chat.inputRef.current?.focus();
    };
    window.addEventListener('ag-insert-prompt', insert as EventListener);
    return () => window.removeEventListener('ag-insert-prompt', insert as EventListener);
  }, [chat]);

  return (
    <div className="flex h-full flex-col bg-slate-950/20">
      <div className="flex-1 overflow-y-auto px-3 py-4 sm:px-4 md:px-8 lg:px-14 xl:px-20">
        {chat.msgs.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <div className="rounded-2xl bg-cyan-500/10 p-5 ring-1 ring-cyan-400/20">
              <Sparkles className="h-9 w-9 text-cyan-300/70" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-200">Ready for the next move</h3>
              <p className="mt-1 max-w-sm text-xs leading-5 text-slate-500">
                Ask the agent to inspect, edit, run, connect tools, or reason across the workspace.
              </p>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {chat.msgs.map((m, i) => (
              <MessageBubble
                key={i}
                {...m}
                sessionId={chat.sessionId}
                onApprove={chat.approve}
              />
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="border-t border-slate-800/60 bg-slate-900/50 px-2.5 py-2.5 sm:px-4 md:px-8 lg:px-14 xl:px-20">
        <div className="mx-auto max-w-3xl">
          <ChatComposer
            input={chat.input}
            streaming={chat.streaming}
            shadowMode={chat.shadowMode}
            modelOptions={chat.modelOptions}
            activeModelId={chat.activeModelId}
            inputRef={chat.inputRef}
            onInput={chat.setInput}
            onSend={chat.send}
            onUpload={chat.upload}
            onToggleShadow={() => chat.setShadowMode(!chat.shadowMode)}
            onModelSelect={chat.setActiveModelId}
          />
          <ActivityRail items={chat.activity} streaming={chat.streaming} />
        </div>
      </div>
    </div>
  );
}

function ActivityRail({ items, streaming }: { items: ChatActivity[]; streaming: boolean }) {
  if (!streaming && items.length === 0) {
    return <p className="mt-1.5 text-center text-[10px] text-slate-600">Live workspace actions use your configured provider and sandbox.</p>;
  }

  const Icon = ({ kind }: { kind: ChatActivity['kind'] }) => {
    if (kind === 'tool') return <Wrench className="h-3 w-3 text-blue-300" />;
    if (kind === 'approval') return <ShieldAlert className="h-3 w-3 text-amber-300" />;
    if (kind === 'done') return <CheckCircle2 className="h-3 w-3 text-emerald-300" />;
    return <CircleDashed className="h-3 w-3 animate-spin text-cyan-300" />;
  };

  return (
    <div className="mt-2 flex flex-wrap items-center justify-center gap-1.5">
      {(items.length ? items : [{ id: 'idle', kind: 'thinking', label: 'Starting backend', detail: 'Opening live stream.' } as ChatActivity]).map((item) => (
        <div key={item.id} className="flex max-w-full items-center gap-1.5 rounded-full border border-slate-800 bg-slate-950/70 px-2.5 py-1 text-[10px] text-slate-400">
          <Icon kind={item.kind} />
          <span className="font-semibold text-slate-300">{item.label}</span>
          {item.detail && <span className="hidden max-w-[260px] truncate text-slate-500 sm:inline">{item.detail}</span>}
        </div>
      ))}
    </div>
  );
}
