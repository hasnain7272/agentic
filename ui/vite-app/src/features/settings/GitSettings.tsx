import { useState, useEffect } from 'react';
import { GitBranch, Key, Lock, Check, Loader2 } from 'lucide-react';
import { apiClient } from '@/api/client';
import { useSessionStore } from '@/store/sessionStore';
import { GitHubConnectButton } from '@/features/github/GitHubConnectButton';

export function GitSettings() {
  const sessionId = useSessionStore(s => s.sessionId);
  const [token, setToken] = useState('');
  const [maskedToken, setMaskedToken] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    apiClient.get<any>(`/sessions/${sessionId}/config`).then(res => {
      if (res.data?.github_token_masked) setMaskedToken(res.data.github_token_masked);
    });
  }, [sessionId]);

  const handleSaveToken = async () => {
    if (!sessionId || !token) return;
    setSaving(true);
    try {
      await apiClient.patch(`/sessions/${sessionId}/config`, { github_token: token });
      setSaved(true);
      setToken('');
      setTimeout(() => setSaved(false), 2000);
      const res = await apiClient.get<any>(`/sessions/${sessionId}/config`);
      if (res.data?.github_token_masked) setMaskedToken(res.data.github_token_masked);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 pt-2">
      <label className="mb-4 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-slate-500/80">
        <GitBranch className="h-3 w-3" />
        GitHub Integration
      </label>
      
      <div className="space-y-4">
        {/* OAuth Option */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h4 className="text-xs font-semibold text-slate-200">Connect via OAuth</h4>
              <p className="mt-1 text-[10px] text-slate-500 leading-relaxed">
                Fastest way to link repositories. Requires server-side configuration.
              </p>
            </div>
            <GitHubConnectButton />
          </div>
        </div>

        {/* PAT Option */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center gap-2 mb-3">
             <Key className="h-3.5 w-3.5 text-cyan-400" />
             <h4 className="text-xs font-semibold text-slate-200">Personal Access Token</h4>
          </div>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Lock className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={maskedToken || "ghp_xxxxxxxxxxxx"}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-9 pr-4 text-xs text-slate-200 focus:border-cyan-500/50 focus:outline-none transition-all"
              />
            </div>
            <button
              onClick={handleSaveToken}
              disabled={saving || !token}
              className="flex items-center gap-1.5 rounded-lg bg-slate-800 px-4 py-2 text-xs font-bold text-slate-200 hover:bg-slate-700 disabled:opacity-50 transition-all border border-slate-700"
            >
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : saved ? <Check className="h-3 w-3 text-green-400" /> : 'Save'}
            </button>
          </div>
          <p className="mt-2 text-[9px] text-slate-600">
            Tokens are encrypted and session-isolated. Recommended for local development.
          </p>
        </div>
      </div>
    </div>
  );
}
