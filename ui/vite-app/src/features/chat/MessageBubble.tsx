import { Bot, User, Wrench } from 'lucide-react';
import { renderContent } from '@/features/chat/renderContent';
import { ToolCallCard } from '@/features/chat/ToolCallCard';
import type { ChatRole, ToolCall } from '@/features/chat/types';
import { ApprovalBlock, BranchButton, ReasoningBlock, StatusMark, StreamingDots } from '@/features/chat/MessageParts';

interface MessageBubbleProps {
  id?: string;
  role: ChatRole;
  content: string;
  streaming?: boolean;
  reasoning?: string;
  tool_calls?: ToolCall[];
  metadata?: Record<string, any>;
  sessionId?: string;
  onApprove?: (id: string, decision: 'approved' | 'denied') => void;
}

const ROLE_CONFIG = {
  user: {
    align: 'ml-auto flex-row-reverse',
    bg: 'bg-gradient-to-br from-cyan-600/25 to-blue-600/15 backdrop-blur-sm border border-cyan-500/20 shadow-md shadow-cyan-950/15',
    ring: '',
    rounding: 'rounded-2xl rounded-tr-none',
    text: 'text-cyan-50',
    icon: User,
    iconColor: 'text-cyan-300 bg-cyan-950/80 border border-cyan-800/40 shadow-sm shadow-cyan-500/10',
    label: 'You',
  },
  assistant: {
    align: 'mr-auto',
    bg: 'bg-slate-900/35 backdrop-blur-sm border border-slate-800/60 shadow-sm shadow-slate-950/40',
    ring: '',
    rounding: 'rounded-2xl rounded-tl-none',
    text: 'text-slate-100',
    icon: Bot,
    iconColor: 'text-violet-300 bg-slate-900 border border-violet-800/30 shadow-sm shadow-violet-500/5',
    label: 'Agent',
  },
  tool: {
    align: 'mr-auto',
    bg: 'bg-slate-950/70 border border-slate-800/60 font-mono shadow-sm',
    ring: '',
    rounding: 'rounded-xl',
    text: 'text-amber-200/90',
    icon: Wrench,
    iconColor: 'text-amber-400 bg-slate-900 border border-amber-900/30',
    label: 'Tool execution log',
  },
  system: {
    align: 'mx-auto',
    bg: 'bg-slate-900/10 border border-slate-800/30 shadow-sm',
    ring: '',
    rounding: 'rounded-xl',
    text: 'text-slate-400/80 text-xs',
    icon: Bot,
    iconColor: 'text-slate-500 bg-slate-900 border border-slate-800/20',
    label: 'System Notification',
  },
};

export function MessageBubble({ id, role, content, streaming, reasoning, tool_calls, metadata, sessionId, onApprove }: MessageBubbleProps) {
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.assistant;
  const Icon = config.icon;

  return (
    <div className={`group relative flex max-w-[88%] gap-3 items-start transition-all duration-200 ${config.align}`}>
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl shadow-md ${config.iconColor}`}>
        <Icon className="h-4 w-4" />
      </div>

      <div className={`flex flex-col min-w-0 ${config.rounding} ${config.bg} px-4.5 py-3 ${config.text}`}>
        <div className="flex items-center justify-between gap-4 mb-1 border-b border-slate-800/30 pb-0.5">
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500/80">{config.label}</span>
          {metadata?.timestamp && (
            <span className="text-[9px] text-slate-600/80 font-medium">
              {new Date(metadata.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
        
        {reasoning && <ReasoningBlock text={reasoning} streaming={streaming} />}
        
        <div className="whitespace-pre-wrap break-words text-sm leading-relaxed font-sans">
          {renderContent(content, sessionId)}
          {streaming && !content && !reasoning && <StreamingDots />}
          {streaming && (content || reasoning) && <StreamingDots />}
        </div>
        
        {metadata?.status === 'NEEDS_APPROVAL' && id && onApprove && (
          <ApprovalBlock id={id} toolName={metadata.tool_name} onApprove={onApprove} />
        )}
        <StatusMark status={metadata?.status} />

        {!!tool_calls?.length && (
          <div className="mt-3 space-y-2">
            {tool_calls.map((tc, i) => <ToolCallCard key={i} call={tc} />)}
          </div>
        )}
      </div>
      
      <BranchButton id={id} role={role} sessionId={sessionId} />
    </div>
  );
}
