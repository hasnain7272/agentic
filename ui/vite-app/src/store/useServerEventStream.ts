import { useEffect, useRef, useState } from 'react';
import { getAuthToken, API_BASE_URL } from '@/api/client';
import { useSessionStore } from './sessionStore';

export type SystemEvent = {
  type: string;
  payload: any;
};

export function useServerEventStream() {
  const [lastEvent, setLastEvent] = useState<SystemEvent | null>(null);
  const [connected, setConnected] = useState(false);
  const sessionId = useSessionStore((s) => s.sessionId);
  const token = getAuthToken();
  const [reconnectTick, setReconnectTick] = useState(0);
  const retryRef = useRef<number | null>(null);

  useEffect(() => {
    if (!sessionId || !token) return;

    const url = `${API_BASE_URL}/api/v1/stream/state?session_id=${encodeURIComponent(sessionId)}&token=${encodeURIComponent(token)}`;
    const evtSource = new EventSource(url, {
      withCredentials: true
    });

    evtSource.onopen = () => setConnected(true);
    
    evtSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastEvent({ type: data.event_type || 'UPDATE', payload: data });
      } catch (e) {
        console.error('Failed to parse SSE', e);
      }
    };

    evtSource.onerror = () => {
      setConnected(false);
      evtSource.close();
      // Reconnect with bounded exponential-ish backoff
      if (retryRef.current) window.clearTimeout(retryRef.current);
      const delayMs = Math.min(15000, 1000 * (2 + reconnectTick));
      retryRef.current = window.setTimeout(() => setReconnectTick((t) => t + 1), delayMs);
    };

    return () => {
      evtSource.close();
      setConnected(false);
      if (retryRef.current) {
        window.clearTimeout(retryRef.current);
        retryRef.current = null;
      }
    };
  }, [sessionId, token, reconnectTick]);

  return { lastEvent, connected };
}
