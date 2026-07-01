import { useEffect, useRef } from 'react';
import { CheckCircle2, CircleDashed, ShieldAlert, Sparkles, Wrench, Loader2 } from 'lucide-react';
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

  // Handle tool progress events from backend
  useEffect(() => {
    const handleToolProgress = (event: Event) => {
      const detail = (event as CustomEvent<{ toolId: string; progress: number; status?: string }>).detail;
      if (!detail) return;
      console.warn('Tool progress event received:', detail);
      // TODO: update UI state for the relevant tool call
    };
    window.addEventListener('tool-progress', handleToolProgress);
    return () => window.removeEventListener('tool-progress', handleToolProgress);
  }, [chat]);

  // Handle websocket disconnect
  useEffect(() => {
    const handleDisconnect = () => {
      console.warn('WebSocket disconnected – showing offline indicator');
    };
    window.addEventListener('websocket-disconnect', handleDisconnect);
    return () => window.removeEventListener('websocket-disconnect', handleDisconnect);
  }, []);

  return (
    <div className="flex h-full flex-col bg-slate-950">
      <div className="flex-1 overflow-y-auto px-3 py-4 sm:px-4 md:px-8 lg:px-14 xl:px-20">
        {chat.msgs.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <div className="rounded-lg bg-slate-900 p-5 ring-1 ring-slate-800">
              <Sparkles className="h-9 w-9 text-emerald-300/70" />
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
            {chat.msgs.map((m) => (
              <MessageBubble
                key={m.id ?? `${m.role}-${m.created_at ?? Date.now()}-${m.content?.slice(0, 50)}`}
                {...m}
                sessionId={chat.sessionId}
                onApprove={chat.approve}
              />
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="border-t border-slate-800 bg-slate-950 px-2.5 py-2.5 sm:px-4 md:px-8 lg:px-14 xl:px-20">
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
