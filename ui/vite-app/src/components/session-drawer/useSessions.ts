import { useCallback, useMemo, useState } from 'react';
import { apiClient } from '@/api/client';
import { useSessionStore } from '@/store/sessionStore';
import { useTaskStore } from '@/store/taskStore';
import type { SessionInfo } from './types';

export function useSessions(onClose: () => void, onOpenSettings: (sessionId: string) => void) {
  const currentSessionId = useSessionStore((s) => s.sessionId);
  const setSessionId = useSessionStore((s) => s.setSessionId);
  const clearTasks = useTaskStore((s) => s.clearTasks);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState('');

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<{ sessions: SessionInfo[] }>('/sessions/');
      const rows = res.data?.sessions || [];
      const enriched = await Promise.all(rows.map(async (session) => {
        const cfg = await apiClient.get<{ model: string; api_key_masked: string }>(`/sessions/${session.id}/config`);
        return { ...session, model: cfg.data?.model || '', has_key: !!cfg.data?.api_key_masked };
      }));
      setSessions(enriched);
    } finally {
      setLoading(false);
    }
  }, []);

  const createSession = async () => {
    setCreating(true);
    try {
      const res = await apiClient.post<{ id: string }>('/sessions/', { name: 'New Session', mode: 'web' });
      if (!res.data?.id) return;
      setSessionId(res.data.id);
      clearTasks();
      await loadSessions();
      onOpenSettings(res.data.id);
    } finally {
      setCreating(false);
    }
  };

  const switchSession = (id: string) => {
    if (id === currentSessionId) return;
    setSessionId(id);
    clearTasks();
    localStorage.removeItem(`ag-chat-${currentSessionId}`);
    onClose();
  };

  const endSession = async (id: string) => {
    await apiClient.delete(`/sessions/${id}`);
    if (id === currentSessionId) {
      const next = sessions.find((session) => session.id !== id);
      if (next) setSessionId(next.id);
    }
    await loadSessions();
  };

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return sessions;
    return sessions.filter((session) => `${session.name} ${session.model || ''} ${session.id}`.toLowerCase().includes(term));
  }, [query, sessions]);

  return { currentSessionId, sessions: filtered, loading, creating, query, setQuery, loadSessions, createSession, switchSession, endSession };
}
