import { useEffect, useRef } from 'react';
import { Sparkles, Loader2, Plus } from 'lucide-react';
import { ChatComposer } from '@/features/chat/ChatComposer';
import { MessageBubble } from '@/features/chat/MessageBubble';
import { ActivityRail } from '@/features/chat/ActivityRail';
import { useChatController } from '@/features/chat/useChatController';
import { useSessionStore } from '@/store/sessionStore';
import { useTaskStore } from '@/store/taskStore';

export function ChatPane() {
  const endRef = useRef<HTMLDivElement>(null);
  const chat = useChatController();
  const sessionId = useSessionStore((s) => s.sessionId);
  const setSessionId = useSessionStore((s) => s.setSessionId);
  const clearTasks = useTaskStore((s) => s.clearTasks);
  const loadSessions = useSessionStore((s) => s.ensureSession);

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

  const hasSession = Boolean(sessionId);
  const canSend = hasSession && chat.modelOptions.length > 0;

  return (
    <div className="flex h-full flex-col bg-[#0c0c0c]">
      <div className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
        <div className="mx-auto max-w-3xl space-y-5">
          {chat.msgs.length === 0 && !hasSession ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[300px] gap-3 text-center">
              <div className="rounded-full bg-emerald-500/10 p-3">
                <Sparkles className="h-7 w-7 text-emerald-500/70" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-300">Welcome to Agentic</h3>
                <p className="mt-1 text-[12px] text-slate-600 max-w-sm">
                  Create a new session from the sidebar to start collaborating with the agent swarm.
                </p>
              </div>
            </div>
          ) : chat.msgs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[300px] gap-3 text-center">
              <div className="rounded-full bg-emerald-500/10 p-3">
                <Sparkles className="h-7 w-7 text-emerald-500/70" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-300">Start a session</h3>
                <p className="mt-1 text-[12px] text-slate-600 max-w-sm">
                  Type a message to begin. The agent can search the web, run analysis, store memories, and integrate with external tools.
                </p>
              </div>
            </div>
          ) : (
            <>
              {chat.msgs.map((m) => (
                <MessageBubble
                  key={m.id ?? `${m.role}-${m.created_at ?? Date.now()}-${m.content?.slice(0, 50)}`}
                  {...m}
                  sessionId={chat.sessionId}
                  onApprove={chat.approve}
                />
              ))}
              {chat.streaming && (
                <div className="flex items-center gap-2 text-[11px] text-slate-500">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Generating...</span>
                </div>
              )}
            </>
          )}
        </div>
        <div ref={endRef} />
      </div>
      <div className="border-t border-[#1e1e1e] bg-[#0c0c0c] p-4">
        <div className="mx-auto max-w-3xl space-y-2">
          <ActivityRail items={chat.activity} streaming={chat.streaming} />
          <ChatComposer
            input={chat.input}
            streaming={chat.streaming}
            modelOptions={chat.modelOptions}
            activeModelId={chat.activeModelId}
            inputRef={chat.inputRef}
            onInput={chat.setInput}
            onSend={canSend ? chat.send : undefined}
            onModelSelect={chat.setActiveModelId}
            disabled={!canSend}
          />
        </div>
      </div>
    </div>
  );
}
