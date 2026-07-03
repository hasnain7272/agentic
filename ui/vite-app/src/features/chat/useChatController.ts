import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient, getAuthToken, WS_BASE_URL } from '@/api/client';
import { useToastStore } from '@/components/Toast';
import { useSessionStore } from '@/store/sessionStore';
import { useTaskStore } from '@/store/taskStore';
import type { ChatActivity, ModelOption, Msg } from '@/features/chat/types';

// Type guard to check if we can send
function canSendMessage(sid: string | null, streaming: boolean, modelOptions: ModelOption[]): boolean {
  return Boolean(sid) && !streaming && modelOptions.length > 0;
}




const eventName = (data: any) => data?.type || data?.event || data?.event_type || '';

export function useChatController() {
  const sid = useSessionStore((s) => s.sessionId);
  const tenantId = useSessionStore((s) => s.tenantId);
  const upsertTask = useTaskStore((s) => s.upsertTask);
  const setActive = useTaskStore((s) => s.setActiveTask);
  const addToast = useToastStore((s) => s.addToast);
  const activeModelId = useSessionStore((s) => s.activeModelId);
  const setActiveModelId = useSessionStore((s) => s.setActiveModelId);

  const [input, setInput] = useState('');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [streaming, setStreaming] = useState(false);

  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [activity, setActivity] = useState<ChatActivity[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const wsRef = useRef<WebSocket | null>(null);


  const loadHistory = useCallback(async () => {
    if (!sid) return;
    const res = await apiClient.get<{ messages: Msg[] }>(`/chat/${sid}/history`);
    if (res.data?.messages?.length) {
      setMsgs(res.data.messages);
    }
  }, [sid]);

  const loadModels = useCallback(async () => {
    const res = await apiClient.get<{ data: ModelOption[] }>('/settings/byok');
    const configured = res.data?.data || [];
    
    const finalModels = configured.map((cfg) => ({
      ...cfg,
      label: cfg.name || cfg.id,
      is_configured: true,
    }));

    setModelOptions(finalModels);
    
    if (!activeModelId || !finalModels.some((m) => m.id === activeModelId)) {
      const fallback = finalModels[0];
      if (fallback?.id) setActiveModelId(fallback.id);
    }
  }, [activeModelId, setActiveModelId]);

  /** Reload chat from storage when session changes, and sync with backend */
  useEffect(() => {
    if (sid) {
      setMsgs([]);
      loadHistory();
    } else {
      setMsgs([]);
    }
    loadModels();
  }, [sid, loadHistory, loadModels]);

  /** Listen for settings reload events */
  useEffect(() => {
    window.addEventListener('refresh-settings', loadModels);
    return () => window.removeEventListener('refresh-settings', loadModels);
  }, [loadModels]);

  const streamTask = useCallback((taskId: string) => {
    wsRef.current?.close();
    const params = new URLSearchParams({ tenant_id: tenantId || localStorage.getItem('tenant_id') || 'local' });
    const token = getAuthToken();
    if (token) params.set('token', token);
    const ws = new WebSocket(`${WS_BASE_URL}/api/v1/tasks/${taskId}/stream?${params}`);
    wsRef.current = ws;
    let contentBuffer = '';
    let reasoningBuffer = '';
    let renderQueued = false;
    let lastTokenActivityAt = 0;
    const pushActivity = (item: ChatActivity) => {
      setActivity((prev) => [item, ...prev.filter((entry) => entry.id !== item.id)].slice(0, 5));
    };
    const flushAssistant = () => {
      renderQueued = false;
      setMsgs((p) => p.map((m, i) =>
        i === p.length - 1 && m.streaming
          ? { ...m, content: contentBuffer, reasoning: reasoningBuffer || m.reasoning }
          : m
      ));
    };
    const scheduleFlush = () => {
      if (renderQueued) return;
      renderQueued = true;
      window.setTimeout(flushAssistant, 50);
    };

    ws.onopen = () => {
      setStreaming(true);
      setActivity([]);
      pushActivity({ id: 'thinking', kind: 'thinking', label: 'Brain connected', detail: 'Waiting for first token or tool decision.' });
      setMsgs((p) => [...p, { role: 'assistant', content: '', streaming: true }]);
    };

    ws.onmessage = (event) => {
      const raw = String(event.data);
      try {
        const data = JSON.parse(raw);

        const kind = eventName(data);

        // Task complete - close cleanly
        if (kind === 'TASK_RESOLVED' || kind === 'done') {
          pushActivity({ id: 'done', kind: 'done', label: 'Task resolved', detail: 'Final response saved to history.' });
          return ws.close();
        }

        if (data.status === 'thinking' || kind === 'connected' || kind === 'state_change') {
          const state = data.state ? String(data.state).replace(/_/g, ' ') : 'Thinking';
          pushActivity({ id: 'thinking', kind: 'thinking', label: data.message || state, detail: kind === 'connected' ? 'Live backend stream opened.' : 'Backend accepted the task.' });
          return;
        }

        // Reasoning tokens (thinking/chain-of-thought)
        if (kind === 'reasoning') {
          reasoningBuffer += data.text;
          pushActivity({ id: 'reasoning', kind: 'thinking', label: 'Reasoning stream', detail: 'Model is planning the next step.' });
          scheduleFlush();
          return;
        }

        // Content tokens
        if (kind === 'token') {
          contentBuffer += data.text;
          const now = Date.now();
          if (now - lastTokenActivityAt > 500) {
            lastTokenActivityAt = now;
            pushActivity({ id: 'token', kind: 'token', label: 'Writing response', detail: `${contentBuffer.length.toLocaleString()} characters streamed.` });
          }
          scheduleFlush();
          return;
        }

        if (kind === 'message') {
          contentBuffer = data.content || data.text || contentBuffer;
          scheduleFlush();
          return;
        }

        // Tool execution events
        if (kind === 'tool_call' || kind === 'tool_start' || kind === 'tool_executing') {
          const name = data.tool || data.name || 'Tool running';
          pushActivity({ id: `tool-${name}`, kind: 'tool', label: name, detail: data.message || 'Governance approved, executing now.' });
          setMsgs((p) => p.map((m, i) =>
            i === p.length - 1
              ? { ...m, tool_calls: [...(m.tool_calls || []), { function: { name, arguments: data.arguments || data.args || '' }, status: 'running' }] }
              : m
          ));
          return;
        }

        if (kind === 'tool_result' || kind === 'tool_progress') {
          const name = data.tool || data.name || 'Tool result';
          const detail = kind === 'tool_result'
            ? (data.result?.success === false ? data.result?.error || 'Tool failed.' : 'Tool completed.')
            : `${data.progress ?? 0}% complete.`;
          pushActivity({ id: `tool-${name}`, kind: 'tool', label: name, detail });
          setMsgs((p) => p.map((m, i) =>
            i === p.length - 1
              ? { ...m, tool_calls: m.tool_calls?.map(tc => tc.function?.name === name ? { ...tc, progress: data.progress, status: kind === 'tool_result' ? 'done' : tc.status } : tc) }
              : m
          ));
          return;
        }

        if (kind === 'approval_required' || kind === 'tool_approval_required') {
          pushActivity({ id: `approval-${data.tool || data.name}`, kind: 'approval', label: 'Approval required', detail: data.tool || data.name || 'A governed tool needs your decision.' });
          setStreaming(false);
          loadHistory(); // Fetch the message with metadata.status = 'NEEDS_APPROVAL'
          return;
        }

        if (kind === 'error') {
          pushActivity({ id: 'error', kind: 'approval', label: 'Backend error', detail: data.error || 'Task failed.' });
          addToast('error', data.error || 'Task failed.');
          return ws.close();
        }
      } catch {
        // Non-JSON output — append to content as raw text
        const clean = raw.replace(/\x1b\[[0-9;]*m/g, '');
        contentBuffer += clean;
      }

      if (contentBuffer.trim()) {
        setMsgs((p) => p.map((m, i) =>
          i === p.length - 1 && m.streaming
            ? { ...m, content: contentBuffer }
            : m
        ));
      }
    };

    ws.onerror = () => { setStreaming(false); addToast('error', 'Live stream disconnected.'); };

    ws.onclose = () => {
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      if (renderQueued) flushAssistant();
      setStreaming(false);
      // Clear activity rail so stale items like "Analyzing..." don't persist
      setActivity([]);
      // Finalize the streaming bubble - keep the streamed content, just mark as not streaming
      setMsgs((p) => {
        const finalized = p.map((m) => m.streaming ? { ...m, streaming: false, content: m.content || contentBuffer } : m);
        // Only reload from backend if we have no assistant content (empty response edge case)
        const lastMsg = finalized[finalized.length - 1];
        if (!lastMsg || !lastMsg.content?.trim()) {
          setTimeout(() => loadHistory(), 800);
        }
        return finalized;
      });
    };
  }, [addToast, loadHistory, tenantId]);

  const send = async () => {
    if (!input.trim() || streaming) return;
    const text = input.trim();

    // Require an active session - user must click "New Session" first
    if (!sid) {
      addToast('info', 'Please click "New Session" to start a conversation.');
      return;
    }

    setInput('');
    setMsgs((p) => [...p, { role: 'user', content: text }]);

    // Get active model from store
    const res = await apiClient.post<{ task_id: string }>('/chat/', {
      session_id: sid,
      message: text,
      active_model_id: useSessionStore.getState().activeModelId || undefined
    });

    if (!res.data?.task_id) return addToast('error', res.error || 'Failed to start task.');
    upsertTask({ id: res.data.task_id, description: text, status: 'running' });
    setActive(res.data.task_id);
    streamTask(res.data.task_id);
  };

  const upload = async (_event: React.ChangeEvent<HTMLInputElement>) => {
    addToast('info', 'File uploads are not supported in database-only mode');
  };

  const approve = async (messageId: string, decision: 'approved' | 'denied') => {
    try {
      await apiClient.post(`/chat/${sid}/approve`, { message_id: messageId, decision });
      await loadHistory();
    } catch (err) {
      addToast('error', 'Approval failed');
    }
  };

  const reset = () => {
    setMsgs([]);
  };

  return {
    sessionId: sid,
    input,
    msgs,
    streaming,
    modelOptions,
    activeModelId,
    activity,
    inputRef,
    setInput,
    send,
    upload,
    approve,
    reset,
    setActiveModelId,
  };
}