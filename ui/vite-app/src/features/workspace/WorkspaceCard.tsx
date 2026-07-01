import React from 'react';

export function WorkspaceCard({ name, type, onRemove }: { name: string; type: string; onRemove?: () => void }) {
  return (
    <div className="flex items-center justify-between p-3 rounded bg-zinc-900 border border-zinc-800 text-zinc-100">
      <div className="flex items-center gap-2">
        <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 capitalize">{type}</span>
        <span className="text-sm font-medium">{name}</span>
      </div>
      {onRemove && (
        <button onClick={onRemove} className="text-zinc-500 hover:text-red-400 text-xs">
          Remove
        </button>
      )}
    </div>
  );
}
