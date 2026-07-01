import { useEffect, useRef, useCallback } from 'react';

/**
 * Reusable SSE hook — subscribes to a Server-Sent Events endpoint
 * and invokes the callback for each incoming message.
 */
export function useSSE(
  url: string | null,
  onMessage: (data: string) => void,
  onError?: () => void,
) {
  const sourceRef = useRef<EventSource | null>(null);
  const cbRef = useRef(onMessage);
  cbRef.current = onMessage;

  const disconnect = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  useEffect(() => {
    if (!url) return;

    const source = new EventSource(url);
    sourceRef.current = source;

    source.onmessage = (event) => cbRef.current(event.data);
    source.onerror = () => {
      onError?.();
      source.close();
    };

    return () => disconnect();
  }, [url, disconnect, onError]);

  return { disconnect };
}
