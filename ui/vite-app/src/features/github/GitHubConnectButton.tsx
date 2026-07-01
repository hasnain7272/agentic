import { useEffect, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { apiClient, API_BASE_URL } from '@/api/client';

interface GitHubUser { login: string; name?: string; avatar_url?: string; id?: number; }
interface GitHubConnectButtonProps {
  sessionId?: string;
  onConnect?: (user: GitHubUser) => void;
  onDisconnect?: () => void;
  compact?: boolean;
}

function GitHubMark() {
  return (
    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.21 11.39.6.11.79-.26.79-.58v-2.23c-3.34.73-4.03-1.42-4.03-1.42-.55-1.39-1.33-1.76-1.33-1.76-1.09-.75.08-.73.08-.73 1.21.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.49 1 .11-.78.42-1.31.76-1.61-2.66-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.12-.3-.54-1.52.12-3.18 0 0 1.01-.32 3.3 1.23A11.5 11.5 0 0 1 12 5.8c1.02.01 2.05.14 3.01.4 2.29-1.55 3.3-1.23 3.3-1.23.65 1.65.24 2.87.12 3.18.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.62-5.48 5.92.43.37.82 1.1.82 2.22v3.29c0 .32.19.69.8.58A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

function ConnectedUser({
  user,
  compact,
  onDisconnect,
}: {
  user: GitHubUser;
  compact: boolean;
  onDisconnect: () => void;
}) {
  if (compact) {
    return (
      <button onClick={onDisconnect} className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-slate-400 transition-colors hover:text-red-400" title={`Connected as ${user.login}`}>
        {user.avatar_url && <img src={user.avatar_url} alt={user.login} className="h-5 w-5 rounded-full" />}
        <span className="text-[10px] font-medium">{user.login}</span>
      </button>
    );
  }
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-700/50 bg-slate-800/60 px-3 py-1.5">
      {user.avatar_url && <img src={user.avatar_url} alt={user.login} className="h-6 w-6 rounded-full" />}
      <span className="text-sm font-medium text-slate-200">{user.login}</span>
      <button onClick={onDisconnect} className="ml-1 text-slate-500 transition-colors hover:text-red-400" title="Disconnect GitHub">
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function GitHubConnectButton({ sessionId, onConnect, onDisconnect, compact = false }: GitHubConnectButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [user, setUser] = useState<GitHubUser | null>(null);
  const [status, setStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const activeSessionId = useSessionStore((s) => s.sessionId);
  const resolvedSessionId = sessionId || activeSessionId;

  useEffect(() => {
    if (!resolvedSessionId) return;
    apiClient.get<{ connected: boolean; user?: GitHubUser }>(`/github/status?session_id=${resolvedSessionId}`).then((res) => {
      setUser(res.data?.connected ? res.data.user || null : null);
      setStatus(res.data?.connected && res.data.user ? 'connected' : 'disconnected');
    });
  }, [resolvedSessionId]);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'github-connected') {
        setUser(event.data.user);
        setStatus('connected');
        onConnect?.(event.data.user);
        setIsLoading(false);
      }
      if (event.data?.type === 'github-error') {
        setStatus('disconnected');
        setIsLoading(false);
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [onConnect]);

  const handleConnect = () => {
    if (!resolvedSessionId) return console.warn('[GitHub] No sessionId provided');
    setIsLoading(true);
    setStatus('connecting');
    const width = 500;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const origin = window.location.origin + window.location.pathname;
    const redirectUri = encodeURIComponent(`${origin.replace(/\/$/, '')}/#/github/callback`);
    const popup = window.open(
      `${API_BASE_URL}/api/v1/github/auth?session_id=${resolvedSessionId}&redirect_uri=${redirectUri}`,
      'github-oauth',
      `width=${width},height=600,left=${left},top=80,popup`
    );
    const checkClosed = setInterval(() => {
      if (!popup?.closed) return;
      clearInterval(checkClosed);
      setIsLoading(false);
      setStatus((current) => current === 'connecting' ? 'disconnected' : current);
    }, 1000);
  };

  const handleDisconnect = async () => {
    if (!resolvedSessionId) return;
    try {
      const res = await apiClient.delete(`/github/disconnect?session_id=${resolvedSessionId}`);
      if (res.data || res.status === 'success') {
        setUser(null);
        setStatus('disconnected');
        onDisconnect?.();
      }
    } catch (error) {
      console.error('[GitHub] Disconnect failed:', error);
    }
  };

  if (status === 'connected' && user) {
    return <ConnectedUser user={user} compact={compact} onDisconnect={handleDisconnect} />;
  }

  return (
    <button
      onClick={handleConnect}
      disabled={isLoading || !resolvedSessionId}
      className={`flex items-center gap-2 rounded-lg border transition-all duration-200 ${compact ? 'px-2 py-1 text-xs' : 'px-4 py-2 text-sm'} ${
        isLoading || !resolvedSessionId
          ? 'cursor-not-allowed border-slate-800 bg-slate-800/40 text-slate-600'
          : 'border-slate-700/50 bg-slate-800/60 text-slate-200 hover:border-slate-600 hover:bg-slate-700'
      }`}
      title={resolvedSessionId ? 'Connect GitHub account' : 'No active session'}
    >
      {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitHubMark />}
      {!compact && <span>{isLoading ? 'Connecting...' : 'Connect GitHub'}</span>}
    </button>
  );
}

export default GitHubConnectButton;
