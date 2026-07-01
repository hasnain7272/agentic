import type { Workspace } from '@/store/sessionStore';
import { IconChevron, IconFolder, IconPlus } from '@/features/workspace/WorkspaceIcons';
import { WorkspaceCard } from '@/features/workspace/WorkspaceCard';

interface Props {
  expanded: boolean;
  workspaces: Workspace[];
  onToggle: () => void;
  onOpen: () => void;
  onRemove: (slug: string) => void;
}

export function WorkspacePanel({ expanded, workspaces, onToggle, onOpen, onRemove }: Props) {
  const local = workspaces.filter((w) => w.type === 'local');
  const git = workspaces.filter((w) => w.type === 'git');

  return (
    <div className="wm-root">
      <button className="wm-header" onClick={onToggle}>
        <div className="wm-header-left">
          <span className={`wm-chevron ${expanded ? 'wm-chevron-open' : ''}`}><IconChevron /></span>
          <span className="wm-header-title">Workspaces</span>
          {!!workspaces.length && <span className="wm-count">{workspaces.length}</span>}
        </div>
        <button className="wm-add-trigger" onClick={(event) => { event.stopPropagation(); onOpen(); }} title="Attach workspace">
          <IconPlus />
        </button>
      </button>
      {expanded && (
        <div className="wm-list">
          {!workspaces.length ? <Empty onOpen={onOpen} /> : (
            <>
              <Group label="Local" tone="wm-dot-local" items={local} onRemove={onRemove} />
              <Group label="Repositories" tone="wm-dot-git" items={git} onRemove={onRemove} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Empty({ onOpen }: { onOpen: () => void }) {
  return (
    <button className="wm-empty" onClick={onOpen}>
      <div className="wm-empty-icon"><IconFolder /></div>
      <span>Attach a project folder or repo</span>
    </button>
  );
}

function Group({ label, tone, items, onRemove }: { label: string; tone: string; items: Workspace[]; onRemove: (slug: string) => void }) {
  if (!items.length) return null;
  return (
    <div className="wm-group">
      <div className="wm-group-label"><span className={`wm-dot ${tone}`} />{label}</div>
      {items.map((ws) => <WorkspaceCard key={ws.slug} ws={ws} onRemove={() => onRemove(ws.slug)} />)}
    </div>
  );
}
