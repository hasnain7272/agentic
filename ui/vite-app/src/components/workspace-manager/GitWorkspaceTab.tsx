import { useState } from 'react';
import { useSessionStore } from '@/store/sessionStore';
import { IconGit } from '@/features/workspace/WorkspaceIcons';
import { GitHubConnectButton } from '@/features/github/GitHubConnectButton';
import { RepoPicker } from '@/features/github/RepoPicker';

interface Props {
  gitUrl: string;
  gitBranch: string;
  inputRef: React.RefObject<HTMLInputElement>;
  onGitUrl: (value: string) => void;
  onGitBranch: (value: string) => void;
  onSubmit: () => void;
}

const branches = ['main', 'develop', 'production'];

export function GitWorkspaceTab({ gitUrl, gitBranch, inputRef, onGitUrl, onGitBranch, onSubmit }: Props) {
  const [showRepos, setShowRepos] = useState(false);
  const sessionId = useSessionStore((s) => s.sessionId);

  return (
    <div className="wm-form">
      <div className="mb-6 flex items-center justify-between rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-slate-400"><IconGit /></div>
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-slate-200">GitHub Studio</p>
            <p className="text-[10px] font-medium text-slate-500">Connect account or paste a repository URL</p>
          </div>
        </div>
        <GitHubConnectButton sessionId={sessionId} compact />
      </div>
      <button
        type="button"
        onClick={() => setShowRepos((value) => !value)}
        className="mb-3 w-full rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-left text-xs font-semibold text-slate-300 transition hover:border-cyan-500/30 hover:bg-slate-900"
      >
        {showRepos ? 'Hide connected repositories' : 'Browse connected GitHub repositories'}
      </button>
      {showRepos && (
        <div className="mb-4">
          <RepoPicker
            onSelect={(repo) => {
              onGitUrl(`https://github.com/${repo.full_name}.git`);
              setShowRepos(false);
            }}
            onCancel={() => setShowRepos(false)}
          />
        </div>
      )}
      <label className="wm-label">Repository URL</label>
      <input ref={inputRef} className="wm-input" placeholder="https://github.com/username/repository.git" value={gitUrl} onChange={(event) => onGitUrl(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && gitUrl.trim() && onSubmit()} />
      <label className="wm-label" style={{ marginTop: 12 }}>Branch</label>
      <div className="wm-branch-row">
        {branches.map((branch) => <button key={branch} className={`wm-branch-chip ${gitBranch === branch ? 'wm-branch-chip-active' : ''}`} onClick={() => onGitBranch(branch)}>{branch}</button>)}
        <input className="wm-input wm-branch-input" placeholder="custom..." value={!branches.includes(gitBranch) ? gitBranch : ''} onChange={(event) => onGitBranch(event.target.value)} />
      </div>
      <p className="wm-hint">Choose the branch to mount into your workspace.</p>
    </div>
  );
}
