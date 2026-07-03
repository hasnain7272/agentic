import { CheckCircle2, Loader2, Wrench, AlertTriangle, Zap, XCircle } from 'lucide-react';
import type { ChatActivity } from '@/features/chat/types';

interface ActivityRailProps {
  items: ChatActivity[];
  streaming: boolean;
}

const iconMap: Record<string, React.ReactNode> = {
  thinking: <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />,
  token: <Zap className="h-3.5 w-3.5 text-emerald-400" />,
  tool: <Wrench className="h-3.5 w-3.5 text-amber-400" />,
  approval: <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />,
  done: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
  error: <XCircle className="h-3.5 w-3.5 text-red-400" />,
};

export function ActivityRail({ items, streaming }: ActivityRailProps) {
  if (!items.length && !streaming) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center gap-2 rounded-md border border-slate-800 bg-slate-900/80 px-2.5 py-1.5 text-xs animate-in fade-in slide-in-from-bottom-1 duration-300"
        >
          {iconMap[item.kind] || iconMap['thinking']}
          <span className="font-medium text-slate-200">{item.label}</span>
          {item.detail && (
            <span className="text-slate-500">{item.detail}</span>
          )}
        </div>
      ))}
      {streaming && items.length === 0 && (
        <div className="flex items-center gap-2 rounded-md border border-slate-800 bg-slate-900/80 px-2.5 py-1.5 text-xs">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />
          <span className="font-medium text-slate-200">Processing...</span>
        </div>
      )}
    </div>
  );
}
