import type { WorkspaceTab } from './types';
import { IconCheck, IconFolder, IconGit, IconX } from '@/features/workspace/WorkspaceIcons';
import { GitWorkspaceTab } from './GitWorkspaceTab';
import { LocalWorkspaceTab } from './LocalWorkspaceTab';

interface Props {
  tab: WorkspaceTab;
  gitUrl: string;
  gitBranch: string;
  loading: boolean;
  inputRef: React.RefObject<HTMLInputElement>;
  onClose: () => void;
  onTab: (tab: WorkspaceTab) => void;
  onGitUrl: (value: string) => void;
  onGitBranch: (value: string) => void;
  onGitAttach: () => void;
  onUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

export function WorkspaceModal(props: Props) {
  const canAttachGit = props.gitUrl.trim() && !props.loading;

  return (
    <div className="wm-overlay" onClick={props.onClose}>
      <div className="wm-modal" onClick={(event) => event.stopPropagation()}>
        <div className="wm-modal-header">
          <h3 className="wm-modal-title">Add Workspace</h3>
          <button className="wm-modal-close" onClick={props.onClose}><IconX /></button>
        </div>
        <div className="wm-modal-tabs">
          <TabButton active={props.tab === 'local'} label="Sandbox Upload" onClick={() => props.onTab('local')}><IconFolder /></TabButton>
          <TabButton active={props.tab === 'git'} label="Git Repository" onClick={() => props.onTab('git')}><IconGit /></TabButton>
        </div>
        <div className="wm-modal-body">
          {props.tab === 'local' ? (
            <LocalWorkspaceTab loading={props.loading} onUpload={props.onUpload} />
          ) : (
            <GitWorkspaceTab gitUrl={props.gitUrl} gitBranch={props.gitBranch} inputRef={props.inputRef} onGitUrl={props.onGitUrl} onGitBranch={props.onGitBranch} onSubmit={props.onGitAttach} />
          )}
        </div>
        <div className="wm-modal-footer">
          <button className="wm-btn-cancel" onClick={props.onClose}>Cancel</button>
          {props.tab === 'git' && (
            <button className="wm-btn-submit" onClick={props.onGitAttach} disabled={!canAttachGit}>
              {props.loading ? <span className="wm-spinner" /> : <><IconCheck /> Attach Repository</>}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function TabButton({ active, label, onClick, children }: { active: boolean; label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button className={`wm-modal-tab ${active ? 'wm-modal-tab-active' : ''}`} onClick={onClick}>
      <div className="flex items-center gap-2"><div className="flex h-5 w-5 items-center justify-center rounded bg-blue-500/10">{children}</div><span>{label}</span></div>
    </button>
  );
}
