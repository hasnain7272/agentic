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
        const cfg = await apiClient.get<{ model: string; api_key_masked: string; byok_config: any }>(`/sessions/${session.id}/config`);
        return { ...session, model: cfg.data?.model || '', has_key: !!cfg.data?.api_key_masked, byokConfig: cfg.data?.byok_config };
      }));
      setSessions(enriched);
    } finally {
      setLoading(false);
    }
  }, []);

  const createSession = async () => {
    setCreating(true);
    try {
      // Backend auto-generates timestamp-based name (e.g., "Session 03 Jul, 16:45")
      // agentic_naming=true (default) will generate name from first user message
      const res = await apiClient.post<{ id: string }>('/sessions/', { agentic_naming: true });
      if (!res.data?.id) return;
      
      const newSessionId = res.data.id;
      // Clear localStorage chat for the new session to ensure clean state
      localStorage.removeItem(`ag-chat-${newSessionId}`);
      // Also clear any existing chat for the old session if switching
      const currentId = useSessionStore.getState().sessionId;
      if (currentId && currentId !== newSessionId) {
        localStorage.removeItem(`ag-chat-${currentId}`);
      }
      
      setSessionId(newSessionId);
      clearTasks();
      await loadSessions();
    } finally {
      setCreating(false);
    }
  };

  const switchSession = (id: string) => {
    if (id === currentSessionId) return;
    // Clear chat for the NEW session to ensure fresh state (preserves old session's chat history)
    localStorage.removeItem(`ag-chat-${id}`);
    setSessionId(id);
    clearTasks();
    onClose();
  };

  const renameSession = async (id: string, name: string) => {
    await apiClient.patch(`/sessions/${id}`, { name });
    await loadSessions();
  };

  const endSession = async (id: string) => {
    await apiClient.delete(`/sessions/${id}`);
    // Clear localStorage chat for deleted session
    localStorage.removeItem(`ag-chat-${id}`);
    if (id === currentSessionId) {
      const next = sessions.find((session) => session.id !== id);
      if (next) {
        setSessionId(next.id);
      } else {
        // No more sessions - go to welcome screen
        setSessionId('');
      }
    }
    await loadSessions();
  };

  // A2A Swarm: Link/unlink sessions for context sharing
  const linkSession = async (sessionId: string, targetId: string) => {
    await apiClient.post(`/sessions/${sessionId}/link`, { target_session_id: targetId });
    await loadSessions();
  };

  const unlinkSession = async (sessionId: string, targetId: string) => {
    await apiClient.delete(`/sessions/${sessionId}/link/${targetId}`);
    await loadSessions();
  };

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return sessions;
    return sessions.filter((session) => `${session.name} ${session.model || ''} ${session.id}`.toLowerCase().includes(term));
  }, [query, sessions]);

  return { 
    currentSessionId, 
    sessions: filtered, 
    loading, 
    creating, 
    query, 
    setQuery, 
    loadSessions, 
    createSession, 
    switchSession, 
    renameSession, 
    endSession,
    linkSession,
    unlinkSession,
  };
}
