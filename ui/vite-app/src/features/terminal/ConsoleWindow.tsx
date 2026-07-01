import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { useSessionStore } from '@/store/sessionStore';
import { useTaskStore } from '@/store/taskStore';
import { getAuthToken, WS_BASE_URL } from '@/api/client';

export function ConsoleWindow() {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const activeTaskId = useTaskStore((s) => s.activeTaskId);
  const tenantId = useSessionStore((s) => s.tenantId);

  useEffect(() => {
    if (!terminalRef.current) return;

    const term = new Terminal({
      theme: { background: '#020617', foreground: '#e2e8f0', cursor: '#3b82f6' },
      fontFamily: 'monospace',
      fontSize: 13,
      disableStdin: false // Allow taking back control!
    });
    
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();
    xtermRef.current = term;

    term.writeln('\x1b[38;5;39m[ANTIGRAVITY OS v3.0]\x1b[0m Kernel attached.');
    
    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit();
      } catch (e) {
        // Ignore fit errors if container is completely hidden
      }
    });
    
    // Slight delay to allow parent flex container to compute dimensions before first fit
    setTimeout(() => {
      try { fitAddon.fit(); } catch(e) {}
    }, 100);

    resizeObserver.observe(terminalRef.current);
    
    return () => {
      resizeObserver.disconnect();
      term.dispose();
    };
  }, []);

  // Subscribe to FastAPI WebSocket
  useEffect(() => {
    if (!activeTaskId || !xtermRef.current) return;
    
    const term = xtermRef.current;
    term.writeln(`\r\n\x1b[38;5;46m[SYSTEM] Establishing WebSocket for Task: ${activeTaskId}...\x1b[0m\r\n`);
    
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const params = new URLSearchParams({ tenant_id: tenantId || 'local' });
    const token = getAuthToken();
    if (token) params.set('token', token);
    const wsUrl = `${WS_BASE_URL}/api/v1/tasks/${activeTaskId}/stream?${params.toString()}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event_type === "TASK_RESOLVED") {
            term.writeln('\r\n\x1b[38;5;46m[SYSTEM] Task complete.\x1b[0m');
            ws.close();
        } else {
            term.writeln(`\x1b[38;5;250m> ${JSON.stringify(data)}\x1b[0m`);
        }
      } catch (e) {
        // If it's not JSON, it's raw text/ANSI tokens from litellm streaming!
        term.write(event.data);
      }
    };

    ws.onerror = () => {
      term.writeln('\r\n\x1b[38;5;196m[ERROR] Connection interupted.\x1b[0m');
    };

    // Forward terminal input to websocket (e.g. Ctrl+C)
    const disposable = term.onData((data) => {
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(data);
        }
    });

    return () => {
        ws.close();
        disposable.dispose();
    };
  }, [activeTaskId]);

  return <div ref={terminalRef} className="h-full w-full overflow-hidden p-2" />;
}
