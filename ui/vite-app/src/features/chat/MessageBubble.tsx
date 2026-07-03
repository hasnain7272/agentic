import { Bot, User, Wrench, ChevronDown } from 'lucide-react';
import { renderContent } from '@/features/chat/renderContent';
import { ToolCallCard } from '@/features/chat/ToolCallCard';
import type { ChatRole, ToolCall } from '@/features/chat/types';
import { ApprovalBlock, ReasoningBlock, StatusMark, StreamingDots } from '@/features/chat/MessageParts';

const ROLE_CONFIG = {
  user: {
    align: 'ml-auto flex-row-reverse',
    bg: 'bg-emerald-500/10 border-emerald-500/20',
    text: 'text-white',
    icon: User,
    iconColor: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    label: 'You',
  },
  assistant: {
    align: 'mr-auto',
    bg: 'bg-[#1e1e1e] border-[#2e2e2e]',
    text: 'text-slate-100',
    icon: Bot,
    iconColor: 'text-slate-400 bg-[#1e1e1e] border-[#2e2e2e]',
    label: 'Agent',
  },
  tool: {
    align: 'mr-auto',
    bg: 'bg-amber-500/10 border-amber-500/20 font-mono',
    text: 'text-amber-200',
    icon: Wrench,
    iconColor: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    label: 'Tool',
  },
  system: {
    align: 'mx-auto',
    bg: 'bg-slate-800/50 border-slate-700/50',
    text: 'text-slate-500 text-xs',
    icon: Bot,
    iconColor: 'text-slate-500 bg-slate-800/50 border-slate-700/50',
    label: 'System',
  },
};

export function MessageBubble({ 
  id, role, content, streaming, reasoning, tool_calls, metadata, sessionId, onApprove 
}: MessageBubbleProps) {
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.assistant;
  const Icon = config.icon;

  return (
    <div className={`group relative flex max-w-[88%] gap-3 items-start transition-all ${config.align}`}>
      <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${config.iconColor}`}>
        <Icon className="h-3.5 w-3.5" />
      </div>

      <div className={`flex flex-col min-w-0 rounded-xl px-4 py-2.5 ${config.bg} ${config.text}`}>
        <div className="flex items-center justify-between gap-2 mb-1 border-b border-slate-800/50 pb-1">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{config.label}</span>
          {metadata?.timestamp && (
            <span className="text-[9px] text-slate-600 font-medium">
              {new Date(metadata.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
        
        {reasoning && <ReasoningBlock text={reasoning} streaming={streaming} />}
        
        <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">
          {renderContent(content, sessionId)}
          {streaming && !content && !reasoning && <StreamingDots />}
          {streaming && (content || reasoning) && <StreamingDots />}
        </div>
        
        {metadata?.status === 'NEEDS_APPROVAL' && id && onApprove && (
          <ApprovalBlock id={id} toolName={metadata.tool_name} onApprove={onApprove} />
        )}
        <StatusMark status={metadata?.status} />

        {!!tool_calls?.length && (
          <div className="mt-2 space-y-1.5">
            {tool_calls.map((tc) => (
              <ToolCallCard key={tc.id ?? `${tc.function?.name}-${tc.status}-${Date.now()}`} call={tc} />
            ))}
          </div>
        )}
      </div>
      
      <div className="flex items-start">
        <ChevronDown className="h-3 w-3 text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity mt-1" />
      </div>
    </div>
  );
}

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