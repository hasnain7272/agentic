import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiClient } from '@/api/client';
import { useServerEventStream } from '@/store/useServerEventStream';
import type { CatalogResponse, DashboardResponse } from './types';

export function useCapabilityStudio() {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const { lastEvent } = useServerEventStream();

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await apiClient.get<CatalogResponse>('/mcp/catalog');
    setCatalog(res.data || null);
    if (!res.data) setError(res.error || 'Capability catalog unavailable.');
    setLoading(false);
  }, []);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await apiClient.get<DashboardResponse>('/mcp/dashboard');
    setDashboard(res.data || null);
    if (!res.data) setError(res.error || 'Capability dashboard unavailable.');
    setLoading(false);
  }, []);

  const refresh = useCallback(async (includeDashboard = false) => {
    await loadCatalog();
    if (includeDashboard) await loadDashboard();
  }, [loadCatalog, loadDashboard]);

  // Dynamic SSE Integration
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.type === 'CATALOG_UPDATED') {
      loadCatalog();
    } else if (lastEvent.type === 'DASHBOARD_UPDATED') {
      loadDashboard();
    }
  }, [lastEvent, loadCatalog, loadDashboard]);

  const counts = useMemo(() => catalog?.summary || {
    tools: catalog?.tools.length || 0,
    skills: catalog?.skills.length || 0,
    plugins: catalog?.plugins.length || 0,
    categories: catalog?.categories.length || 0,
    ready_skills: catalog?.skills.filter((skill) => skill.ready).length || 0,
    missing_skill_tools: catalog?.skills.reduce((sum, skill) => sum + (skill.missing_tools?.length || 0), 0) || 0,
    stdio_servers: 0,
    stdio_running: 0,
  }, [catalog]);

  return { catalog, dashboard, loading, error, counts, loadCatalog, loadDashboard, refresh };
}
