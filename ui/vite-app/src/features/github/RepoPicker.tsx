import { useCallback, useEffect, useState } from 'react';
import { FolderGit2, Loader2, Lock, Search } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { apiClient } from '@/api/client';

interface Repo {
  id: number;
  name: string;
  full_name: string;
  description?: string;
  private: boolean;
  updated_at: string;
}

interface RepoPickerProps {
  onSelect: (repo: Repo) => void;
  onCancel?: () => void;
}

function RepoRow({ repo, onSelect }: { repo: Repo; onSelect: (repo: Repo) => void }) {
  const Icon = repo.private ? Lock : FolderGit2;
  return (
    <button
      onClick={() => onSelect(repo)}
      className="flex w-full items-start gap-3 border-b border-slate-800/50 px-4 py-3 text-left transition-colors hover:bg-slate-800"
    >
      <Icon className={`mt-0.5 h-4 w-4 ${repo.private ? 'text-yellow-500' : 'text-slate-500'}`} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-200">{repo.full_name}</p>
        {repo.description && <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">{repo.description}</p>}
      </div>
    </button>
  );
}

export const RepoPicker = ({ onSelect, onCancel }: RepoPickerProps) => {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [search, setSearch] = useState('');
  const sessionId = useSessionStore((s) => s.sessionId);

  const fetchRepos = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await apiClient.get<{ repos: Repo[] }>(`/github/repos?session_id=${sessionId}&page=${page}`);
      const next = res.data?.repos || [];
      setRepos((prev) => (page === 1 ? next : [...prev, ...next]));
      setHasMore(next.length === 30);
    } catch (err) {
      console.error('Failed to fetch repos:', err);
    } finally {
      setLoading(false);
    }
  }, [page, sessionId]);

  useEffect(() => {
    fetchRepos();
  }, [fetchRepos]);

  const filteredRepos = repos.filter((repo) => {
    const term = search.toLowerCase();
    return repo.name.toLowerCase().includes(term) || repo.full_name.toLowerCase().includes(term);
  });

  return (
    <div className="w-full max-w-md overflow-hidden rounded-xl border border-slate-700 bg-slate-900 shadow-2xl max-sm:max-w-[calc(100vw-1.5rem)]">
      <div className="border-b border-slate-700 p-4">
        <h3 className="text-lg font-semibold text-white">Select Repository</h3>
        <p className="mt-1 text-sm text-slate-400">Choose the project context for this session.</p>
      </div>

      <div className="relative border-b border-slate-700 p-4">
        <Search className="pointer-events-none absolute left-7 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search repositories..."
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-9 py-2 text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-blue-500"
        />
      </div>

      <div className="max-h-96 overflow-y-auto">
        {loading && page === 1 ? (
          <div className="p-8 text-center text-sm text-slate-500">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-blue-500" />
            <p className="mt-3">Loading repositories...</p>
          </div>
        ) : filteredRepos.length === 0 ? (
          <div className="p-8 text-center text-slate-500">No repositories found</div>
        ) : (
          <>
            {filteredRepos.map((repo) => <RepoRow key={repo.id} repo={repo} onSelect={onSelect} />)}
            {hasMore && (
              <button onClick={() => setPage((p) => p + 1)} disabled={loading} className="w-full py-3 text-sm text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-200">
                {loading ? 'Loading...' : 'Load more'}
              </button>
            )}
          </>
        )}
      </div>

      <div className="flex justify-end border-t border-slate-700 bg-slate-800/50 p-4">
        <button onClick={onCancel} className="px-4 py-2 text-sm text-slate-400 transition-colors hover:text-white">Cancel</button>
      </div>
    </div>
  );
};

export default RepoPicker;
