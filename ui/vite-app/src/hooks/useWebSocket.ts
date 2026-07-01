import { useCallback, useEffect, useRef, useState } from 'react';
import { getAuthToken, WS_BASE_URL } from '@/api/client';

interface WebSocketMessage {
  data: unknown;
  timestamp: number;
}

interface UseWebSocketOptions {
  autoReconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (error: Event) => void;
  onMessage?: (data: unknown) => void;
}

const parsePayload = (value: string) => {
  try { return JSON.parse(value) as unknown; }
  catch { return value; }
};

export function useWebSocket(path: string, options: UseWebSocketOptions = {}) {
  const {
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    onOpen,
    onClose,
    onError,
    onMessage,
  } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const attemptsRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queueRef = useRef<unknown[]>([]);

  const url = useCallback(() => {
    const token = getAuthToken();
    const suffix = token && !path.includes('token=') ? `${path.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}` : '';
    return `${WS_BASE_URL}${path}${suffix}`;
  }, [path]);

  const clearTimer = () => {
    if (!timerRef.current) return;
    clearTimeout(timerRef.current);
    timerRef.current = null;
  };

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setIsConnecting(true);
    setConnectionError(null);

    try {
      const ws = new WebSocket(url());
      wsRef.current = ws;
      ws.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
        attemptsRef.current = 0;
        while (queueRef.current.length) ws.send(JSON.stringify(queueRef.current.shift()));
        onOpen?.();
      };
      ws.onclose = (event) => {
        setIsConnected(false);
        setIsConnecting(false);
        onClose?.(event);
        if (!autoReconnect || attemptsRef.current >= maxReconnectAttempts) return;
        attemptsRef.current += 1;
        timerRef.current = setTimeout(connect, reconnectInterval * attemptsRef.current);
      };
      ws.onerror = (error) => {
        setConnectionError('Connection failed');
        onError?.(error);
      };
      ws.onmessage = (event) => {
        const data = parsePayload(String(event.data));
        setLastMessage({ data, timestamp: Date.now() });
        onMessage?.(data);
      };
    } catch {
      setConnectionError('Failed to connect');
      setIsConnecting(false);
    }
  }, [autoReconnect, maxReconnectAttempts, onClose, onError, onMessage, onOpen, reconnectInterval, url]);

  const disconnect = useCallback(() => {
    clearTimer();
    attemptsRef.current = maxReconnectAttempts;
    wsRef.current?.close();
    wsRef.current = null;
  }, [maxReconnectAttempts]);

  const sendMessage = useCallback((data: unknown) => {
    const message = typeof data === 'string' ? data : JSON.stringify(data);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(message);
      return true;
    }
    queueRef.current.push(data);
    return false;
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    attemptsRef.current = 0;
    connect();
  }, [connect, disconnect]);

  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);

  return { isConnected, isConnecting, lastMessage, connectionError, sendMessage, connect, disconnect, reconnect };
}

export default useWebSocket;
