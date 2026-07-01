import React from 'react';

export function DiffViewer({ diff }: { diff: string }) {
  return (
    <pre className="p-3 rounded bg-zinc-950 border border-zinc-800 text-xs font-mono overflow-auto max-h-60 text-zinc-300">
      {diff || "No changes to show."}
    </pre>
  );
}
