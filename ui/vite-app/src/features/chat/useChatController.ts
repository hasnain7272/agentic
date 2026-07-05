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
  const activeTaskId = useTaskStore((s) => s.activeTaskId);
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
    let reconnectAttempts = 0;
    const maxReconnects = 3;

    function startStream() {
      if (reconnectAttempts >= maxReconnects) {
        setStreaming(false);
        addToast('error', 'Live stream connection failed after multiple attempts.');
        return;
      }

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
        reconnectAttempts = 0; // reset
        setMsgs((p) => {
          const last = p[p.length - 1];
          if (last && last.role === 'assistant') {
            contentBuffer = last.content || '';
            reasoningBuffer = last.reasoning || '';
            return p.map((m, idx) => idx === p.length - 1 ? { ...m, streaming: true } : m);
          }
          contentBuffer = '';
          reasoningBuffer = '';
          const clientMsgId = `client-${Math.random().toString(36).substring(2, 11)}`;
          return [...p, { id: clientMsgId, role: 'assistant', content: '', streaming: true }];
        });
      };

      ws.onmessage = (event) => {
        const raw = String(event.data);
        try {
          const data = JSON.parse(raw);
          const kind = eventName(data);

          if (kind === 'heartbeat') {
            return; // ignore silently
          }

          if (kind === 'TASK_RESOLVED' || kind === 'done') {
            pushActivity({ id: 'done', kind: 'done', label: 'Task resolved', detail: 'Final response saved to history.' });
            reconnectAttempts = maxReconnects; // prevent reconnect
            return ws.close();
          }

          if (data.status === 'thinking' || kind === 'connected' || kind === 'state_change') {
            const state = data.state ? String(data.state).replace(/_/g, ' ') : 'Thinking';
            pushActivity({ id: 'thinking', kind: 'thinking', label: data.message || state, detail: kind === 'connected' ? 'Live backend stream opened.' : 'Backend accepted the task.' });
            return;
          }

          if (kind === 'reasoning') {
            reasoningBuffer += data.text;
            pushActivity({ id: 'reasoning', kind: 'thinking', label: 'Reasoning stream', detail: 'Model is planning the next step.' });
            scheduleFlush();
            return;
          }

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
                ? {
                  ...m,
                  tool_calls: m.tool_calls?.map(tc =>
                    tc.function?.name === name
                      ? {
                        ...tc,
                        progress: data.progress,
                        status: kind === 'tool_result' ? (data.result?.success === false ? 'failed' : 'done') : tc.status,
                        result: kind === 'tool_result' ? data.result?.data : tc.result,
                        error: kind === 'tool_result' ? data.result?.error : tc.error,
                        completed_at: kind === 'tool_result' ? new Date().toISOString() : tc.completed_at
                      }
                      : tc
                  )
                }
                : m
            ));
            return;
          }

          if (kind === 'approval_required' || kind === 'tool_approval_required') {
            pushActivity({ id: `approval-${data.tool || data.name}`, kind: 'approval', label: 'Approval required', detail: data.tool || data.name || 'A governed tool needs your decision.' });
            setStreaming(false);
            loadHistory();
            return;
          }

          if (kind === 'error') {
            pushActivity({ id: 'error', kind: 'approval', label: 'Backend error', detail: data.error || 'Task failed.' });
            addToast('error', data.error || 'Task failed.');
            reconnectAttempts = maxReconnects; // prevent reconnect
            return ws.close();
          }
        } catch {
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

      ws.onerror = () => {
        // ws.onclose handles retry
      };

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        if (renderQueued) flushAssistant();

        if (reconnectAttempts < maxReconnects) {
          reconnectAttempts++;
          const delay = Math.pow(2, reconnectAttempts) * 1000;
          pushActivity({ id: 'reconnection', kind: 'thinking', label: 'Reconnecting...', detail: `Stream interrupted. Reconnecting in ${delay / 1000}s (Attempt ${reconnectAttempts}/${maxReconnects}).` });
          setTimeout(startStream, delay);
        } else {
          setStreaming(false);
          setActivity([]);
          setMsgs((p) => {
            const finalized = p.map((m) => m.streaming ? { ...m, streaming: false, content: m.content || contentBuffer } : m);
            const lastMsg = finalized[finalized.length - 1];
            if (!lastMsg || !lastMsg.content?.trim()) {
              setTimeout(() => loadHistory(), 800);
            }
            return finalized;
          });
        }
      };
    }

    startStream();
  }, [addToast, loadHistory, tenantId]);

  const send = async () => {
    if (!input.trim() || streaming) return;
    const text = input.trim();

    if (!sid) {
      addToast('info', 'Please click "New Session" to start a conversation.');
      return;
    }

    setInput('');
    const clientMsgId = `client-${Math.random().toString(36).substring(2, 11)}`;
    setMsgs((p) => [...p, { id: clientMsgId, role: 'user', content: text }]);

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
      if (activeTaskId) {
        streamTask(activeTaskId);
      }
    } catch (err) {
      addToast('error', 'Approval failed');
    }
  };

  const stop = useCallback(async () => {
    if (!activeTaskId) return;
    try {
      await apiClient.post(`/tasks/${activeTaskId}/stop`);
    } catch (err) {
      console.error('Failed to cancel task:', err);
    }
    wsRef.current?.close();
  }, [activeTaskId]);

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
    stop,
    upload,
    approve,
    reset,
    setActiveModelId,
  };
}