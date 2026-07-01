import { useEffect, useRef, useState } from 'react';
import { Pencil } from 'lucide-react';
import { apiClient } from '@/api/client';

interface Props {
  sessionId: string;
  name: string;
  onRename: () => void;
}

export function EditableSessionName({ sessionId, name, onRename }: Props) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(name);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const save = async () => {
    const next = value.trim();
    if (next && next !== name) {
      await apiClient.patch(`/sessions/${sessionId}/name`, { name: next });
      onRename();
    }
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onBlur={save}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => { if (event.key === 'Enter') save(); if (event.key === 'Escape') setEditing(false); }}
        className="w-full rounded bg-slate-800 px-1.5 py-0.5 text-[11px] font-medium text-slate-200 outline-none ring-1 ring-cyan-500/40"
        maxLength={64}
      />
    );
  }

  return (
    <div className="group/name flex items-center gap-1">
      <span className="truncate text-[11px] font-medium text-slate-200">{name}</span>
      <button onClick={(event) => { event.stopPropagation(); setEditing(true); }} className="shrink-0 rounded p-0.5 text-slate-600 opacity-0 transition hover:text-cyan-400 group-hover/name:opacity-100">
        <Pencil className="h-2.5 w-2.5" />
      </button>
    </div>
  );
}
