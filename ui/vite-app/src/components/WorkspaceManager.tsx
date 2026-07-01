import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '@/api/client';
import { useSessionStore, type Workspace } from '@/store/sessionStore';
import { workspaceStyles } from '@/features/workspace/WorkspaceStyles';
import { WorkspaceModal } from './workspace-manager/WorkspaceModal';
import { WorkspacePanel } from './workspace-manager/WorkspacePanel';
import type { WorkspaceTab } from './workspace-manager/types';

interface WorkspaceManagerProps {
  externalOpen?: boolean;
  onExternalClose?: () => void;
}

export function WorkspaceManager({ externalOpen, onExternalClose }: WorkspaceManagerProps = {}) {
  const workspaces = useSessionStore((s) => s.workspaces);
  const addWorkspace = useSessionStore((s) => s.addWorkspace);
  const removeWorkspace = useSessionStore((s) => s.removeWorkspace);
  const sessionId = useSessionStore((s) => s.sessionId);
  const [expanded, setExpanded] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [tab, setTab] = useState<WorkspaceTab>('local');
  const [gitUrl, setGitUrl] = useState('');
  const [gitBranch, setGitBranch] = useState('main');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const isModalOpen = showModal || !!externalOpen;
  const isExternalOnly = externalOpen !== undefined;

  const closeModal = () => {
    setShowModal(false);
    onExternalClose?.();
  };

  useEffect(() => {
    if (isModalOpen) setTimeout(() => inputRef.current?.focus(), 100);
  }, [isModalOpen, tab]);

  const attachGit = useCallback(async () => {
    if (loading || !gitUrl.trim()) return;
    setLoading(true);
    try {
      const ws: Workspace = { type: 'git', url: gitUrl.trim(), branch: gitBranch.trim() || 'main', slug: '' };
      await addWorkspace(ws);
      setGitUrl('');
      setGitBranch('main');
      closeModal();
    } finally {
      setLoading(false);
    }
  }, [addWorkspace, gitBranch, gitUrl, loading]);

  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files?.length || !sessionId) return;
    setLoading(true);
    try {
      const formData = new FormData();
      Array.from(files).forEach((file) => formData.append('files', file, file.name));
      await apiClient.post(`/workspace/sessions/${sessionId}/upload`, formData);
      closeModal();
      window.dispatchEvent(new Event('refresh-workspace'));
    } finally {
      setLoading(false);
    }
  };

  if (!sessionId) return null;

  return (
    <>
      {!isExternalOnly && (
        <WorkspacePanel
          expanded={expanded}
          workspaces={workspaces}
          onToggle={() => setExpanded((value) => !value)}
          onOpen={() => setShowModal(true)}
          onRemove={removeWorkspace}
        />
      )}
      {isModalOpen && (
        <WorkspaceModal
          tab={tab}
          gitUrl={gitUrl}
          gitBranch={gitBranch}
          loading={loading}
          inputRef={inputRef}
          onClose={closeModal}
          onTab={setTab}
          onGitUrl={setGitUrl}
          onGitBranch={setGitBranch}
          onGitAttach={attachGit}
          onUpload={upload}
        />
      )}
      <style>{workspaceStyles}</style>
    </>
  );
}
