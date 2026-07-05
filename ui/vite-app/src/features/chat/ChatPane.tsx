import { useEffect, useRef, Component, ErrorInfo, ReactNode } from 'react';
import { Sparkles, Loader2 } from 'lucide-react';
import { ChatComposer } from '@/features/chat/ChatComposer';
import { MessageBubble } from '@/features/chat/MessageBubble';
import { useChatController } from '@/features/chat/useChatController';
import { useSessionStore } from '@/store/sessionStore';

interface ErrorBoundaryProps {
  children?: ReactNode;
}
interface ErrorBoundaryState {
  hasError: boolean;
}
class MessageErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = { hasError: false };
  public static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }
  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Message bubble render error:", error, errorInfo);
  }
  public render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-xl border border-red-900/30 bg-red-950/20 p-3 text-xs text-red-300">
          <span className="font-semibold block mb-0.5">Render Error</span>
          <span className="text-[11px] text-slate-500">Failed to render message bubble.</span>
        </div>
      );
    }
    return this.props.children;
  }
}

export function ChatPane() {
  const endRef = useRef<HTMLDivElement>(null);
  const chat = useChatController();
  const sessionId = useSessionStore((s) => s.sessionId);

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
                <MessageErrorBoundary key={m.id ?? `${m.role}-${m.created_at ?? Date.now()}-${m.content?.slice(0, 50)}`}>
                  <MessageBubble
                    {...m}
                    sessionId={chat.sessionId}
                    onApprove={chat.approve}
                  />
                </MessageErrorBoundary>
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
        <div className="mx-auto max-w-3xl">
          <ChatComposer
            input={chat.input}
            streaming={chat.streaming}
            modelOptions={chat.modelOptions}
            activeModelId={chat.activeModelId}
            inputRef={chat.inputRef}
            onInput={chat.setInput}
            onSend={chat.send}
            onStop={chat.stop}
            onModelSelect={chat.setActiveModelId}
            disabled={!canSend}
          />
        </div>
      </div>
    </div>
  );
}
