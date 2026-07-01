import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient, getAuthToken, WS_BASE_URL } from '@/api/client';
import { useToastStore } from '@/components/Toast';
import { useSessionStore } from '@/store/sessionStore';
import { useTaskStore } from '@/store/taskStore';
import { PRESETS } from '@/features/settings/LLMSettings';
import type { ChatActivity, ModelOption, Msg } from '@/features/chat/types';

/** Session-scoped localStorage key for chat messages. */
const chatKey = (sid: string) => `ag-chat-${sid}`;

const fromStorage = (sid: string): Msg[] => {
  if (!sid) return [];
  try { return JSON.parse(localStorage.getItem(chatKey(sid)) || '[]') as Msg[]; }
  catch { return []; }
};

export function useChatController() {
  const sid = useSessionStore((s) => s.sessionId);
  const tenantId = useSessionStore((s) => s.tenantId);
  const upsertTask = useTaskStore((s) => s.upsertTask);
  const setActive = useTaskStore((s) => s.setActiveTask);
  const addToast = useToastStore((s) => s.addToast);
  const activeModelId = useSessionStore((s) => s.activeModelId);
  const setActiveModelId = useSessionStore((s) => s.setActiveModelId);

  const [input, setInput] = useState('');
  const [msgs, setMsgs] = useState<Msg[]>(() => fromStorage(sid));
  const [streaming, setStreaming] = useState(false);
  const [shadowMode, setShadowMode] = useState(false);
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [activity, setActivity] = useState<ChatActivity[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  /** Persist to session-scoped key */
  useEffect(() => {
    if (sid && msgs.length) localStorage.setItem(chatKey(sid), JSON.stringify(msgs));
  }, [msgs, sid]);

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
    
    // We always want to show all presets in the dropdown. 
    // If a preset is configured in the backend, we merge its actual configured settings.
    const merged = PRESETS.map((preset) => {
      const cfg = configured.find((c) => c.id === preset.id);
      if (cfg) {
        return {
          ...preset,
          ...cfg,
          label: cfg.label || cfg.name || preset.label,
          provider: cfg.provider || preset.provider || (cfg.base_url?.includes('nvidia.com') ? 'NVIDIA' : 'Custom'),
          is_configured: true,
        };
      }
      return {
        ...preset,
        is_configured: false,
      };
    });

    // We also want to include any custom configured models that are not in PRESETS
    const customConfigured = configured
      .filter((cfg) => !PRESETS.some((preset) => preset.id === cfg.id))
      .map((cfg) => ({
        ...cfg,
        label: cfg.label || cfg.name || cfg.id,
        provider: cfg.provider || 'Custom',
        is_configured: true,
      }));

    const finalModels = [...merged, ...customConfigured];
    setModelOptions(finalModels);
    
    // Set default active model: prefer a configured model over an unconfigured preset
    if (!activeModelId || !finalModels.some((m) => m.id === activeModelId)) {
      const firstConfigured = finalModels.find((m) => m.is_configured);
      const fallback = firstConfigured || finalModels[0];
      if (fallback?.id) setActiveModelId(fallback.id);
    }
  }, [activeModelId, setActiveModelId]);

  /** Reload chat from storage when session changes, and sync with backend */
  useEffect(() => {
    setMsgs(fromStorage(sid));
    loadHistory();
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

        // Task complete — close cleanly
        if (data.event_type === 'TASK_RESOLVED' || data.event === 'TASK_RESOLVED') {
          pushActivity({ id: 'done', kind: 'done', label: 'Task resolved', detail: 'Final response saved to history.' });
          return ws.close();
        }

        if (data.status === 'thinking') {
          pushActivity({ id: 'thinking', kind: 'thinking', label: data.message || 'Thinking', detail: 'Backend accepted the task.' });
          return;
        }

        // Reasoning tokens (thinking/chain-of-thought)
        if (data.event === 'reasoning') {
          reasoningBuffer += data.text;
          pushActivity({ id: 'reasoning', kind: 'thinking', label: 'Reasoning stream', detail: 'Model is planning the next step.' });
          scheduleFlush();
          return;
        }

        // Content tokens
        if (data.event === 'token') {
          contentBuffer += data.text;
          const now = Date.now();
          if (now - lastTokenActivityAt > 500) {
            lastTokenActivityAt = now;
            pushActivity({ id: 'token', kind: 'token', label: 'Writing response', detail: `${contentBuffer.length.toLocaleString()} characters streamed.` });
          }
          scheduleFlush();
          return;
        }

        // Tool execution events
        if (data.event === 'tool_start' || data.event === 'tool_executing') {
          pushActivity({ id: `tool-${data.name}`, kind: 'tool', label: data.name || 'Tool running', detail: data.message || 'Governance approved, executing now.' });
          setMsgs((p) => p.map((m, i) =>
            i === p.length - 1
              ? { ...m, tool_calls: [...(m.tool_calls || []), { function: { name: data.name, arguments: data.args || '' }, status: 'running' }] }
              : m
          ));
          return;
        }

        if (data.event === 'tool_progress') {
          pushActivity({ id: `tool-${data.name}`, kind: 'tool', label: data.name || 'Tool progress', detail: `${data.progress ?? 0}% complete.` });
          setMsgs((p) => p.map((m, i) =>
            i === p.length - 1
              ? { ...m, tool_calls: m.tool_calls?.map(tc => tc.function?.name === data.name ? { ...tc, progress: data.progress } : tc) }
              : m
          ));
          return;
        }

        if (data.event === 'tool_approval_required') {
          pushActivity({ id: `approval-${data.name}`, kind: 'approval', label: 'Approval required', detail: data.name || 'A governed tool needs your decision.' });
          setStreaming(false);
          loadHistory(); // Fetch the message with metadata.status = 'NEEDS_APPROVAL'
          return;
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
      // Finalize the streaming bubble
      setMsgs((p) => p.map((m) => m.streaming ? { ...m, streaming: false } : m));
      // Reload authoritative history from backend
      setTimeout(() => {
        setStreaming(false); // Double tap to ensure state unlocks
        loadHistory();
      }, 500);
    };
  }, [addToast, loadHistory, tenantId]);

  const send = async () => {
    if (!input.trim() || streaming) return;
    const text = input.trim();
    setInput('');
    setMsgs((p) => [...p, { role: 'user', content: text }]);

    // Get active model from store
    const res = await apiClient.post<{ task_id: string }>('/chat/', {
      session_id: sid,
      message: text,
      shadow_mode: shadowMode,
      active_model_id: useSessionStore.getState().activeModelId || undefined
    });

    if (!res.data?.task_id) return addToast('error', res.error || 'Failed to start task.');
    upsertTask({ id: res.data.task_id, description: text, status: 'running' });
    setActive(res.data.task_id);
    streamTask(res.data.task_id);
  };

  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !sid) return;
    const body = new FormData();
    body.append('files', file);
    addToast('info', 'Uploading...');
    const res = await apiClient.post(`/workspace/sessions/${sid}/upload`, body);
    if (!res.data) return addToast('error', res.error || 'Upload failed');
    addToast('success', 'File uploaded');
    setMsgs((p) => [...p, { role: 'system', content: `Attached: ${file.name}` }]);
    window.dispatchEvent(new Event('refresh-workspace'));
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
    localStorage.removeItem(chatKey(sid));
    setMsgs([]);
  };

  return {
    sessionId: sid,
    input,
    msgs,
    streaming,
    shadowMode,
    modelOptions,
    activeModelId,
    activity,
    inputRef,
    setInput,
    send,
    upload,
    approve,
    reset,
    setShadowMode,
    setActiveModelId,
  };
}
