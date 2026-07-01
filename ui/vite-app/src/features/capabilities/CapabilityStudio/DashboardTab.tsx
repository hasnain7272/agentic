import React, { useState } from 'react';
import { Activity, Plug, CheckCircle, AlertTriangle, TrendingUp, Clock, X } from 'lucide-react';
import type { DashboardResponse } from './types';
import { apiClient } from '@/api/client';

interface Props { dashboard: DashboardResponse | null; onDashboardChanged: () => void; }

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { color: string; bg: string; icon: typeof CheckCircle }> = {
    active: { color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30', icon: CheckCircle },
    rate_limited: { color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30', icon: Clock },
    error: { color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', icon: AlertTriangle },
    disabled: { color: 'text-slate-400', bg: 'bg-slate-500/10 border-slate-500/30', icon: X },
  };
  const { color, bg, icon: Icon } = config[status] || config['disabled'];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider ${color} ${bg}`}>
      <Icon className="h-3 w-3" />
      {status}
    </span>
  );
}

function MetricCard({ label, value, subvalue, icon: Icon, color }: { label: string; value: string | number; subvalue?: string; icon: typeof TrendingUp; color: string; }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-center gap-2">
        <div className={`rounded-lg p-1.5 ${color}`}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <div className="mt-2 text-2xl font-bold text-slate-100">{value}</div>
      {subvalue && <div className="mt-1 text-[11px] text-slate-500">{subvalue}</div>}
    </div>
  );
}

export function DashboardTab({ dashboard, onDashboardChanged }: Props) {
  const [unregistering, setUnregistering] = useState<string | null>(null);
  const [message, setMessage] = useState('');

  const unregisterPlugin = async (pluginName: string) => {
    setUnregistering(pluginName);
    const res = await apiClient.delete<{ message: string }>(`/mcp/${pluginName}`);
    setUnregistering(null);
    if (res.data) {
      setMessage(`Plugin '${pluginName}' unregistered.`);
      onDashboardChanged();
    } else {
      setMessage(res.error || 'Failed to unregister plugin.');
    }
  };

  if (!dashboard) return null;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Total Plugins" value={dashboard.total_count} subvalue="registered" icon={Plug} color="bg-violet-500/10 text-violet-400" />
        <MetricCard label="Healthy" value={dashboard.healthy_count} subvalue="active" icon={CheckCircle} color="bg-emerald-500/10 text-emerald-400" />
        <MetricCard label="Circuit Open" value={dashboard.circuit_open_count} subvalue="degraded" icon={AlertTriangle} color="bg-amber-500/10 text-amber-400" />
        <MetricCard label="Total Calls" value={dashboard.plugins.reduce((acc, p) => acc + p.total_calls, 0)} subvalue="all time" icon={TrendingUp} color="bg-cyan-500/10 text-cyan-400" />
      </div>

      {dashboard.plugins.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/40 p-8 text-center">
          <Activity className="mx-auto h-8 w-8 text-slate-600" />
          <p className="mt-3 text-sm text-slate-500">No MCP plugins registered yet.</p>
          <p className="mt-1 text-xs text-slate-600">Go to the Plugins tab to register your first MCP tool.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-slate-300">Plugin Health</h3>
          {dashboard.plugins.map((plugin) => (
            <div key={plugin.name} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <Plug className="h-4 w-4 text-emerald-400" />
                    <span className="text-sm font-semibold text-slate-100">{plugin.name}</span>
                    <StatusBadge status={plugin.status} />
                  </div>
                  {plugin.endpoint_url && <p className="mt-1 text-[11px] text-slate-500">{plugin.endpoint_url}</p>}
                  <p className="mt-2 text-sm text-slate-400">{plugin.description}</p>

                  <div className="mt-4 grid grid-cols-4 gap-4">
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Calls</div>
                      <div className="text-sm font-semibold text-slate-200">{plugin.total_calls}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Failures</div>
                      <div className="text-sm font-semibold text-slate-200">{plugin.failed_calls}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Success</div>
                      <div className={`text-sm font-semibold ${plugin.success_rate >= 0.9 ? 'text-emerald-400' : plugin.success_rate >= 0.7 ? 'text-amber-400' : 'text-red-400'}`}>
                        {(plugin.success_rate * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Latency</div>
                      <div className="text-sm font-semibold text-slate-200">{plugin.avg_latency_ms.toFixed(0)}ms</div>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => unregisterPlugin(plugin.name)}
                  disabled={unregistering === plugin.name}
                  className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-400 transition hover:bg-red-500/20 disabled:opacity-50"
                >
                  {unregistering === plugin.name ? 'Removing...' : 'Unregister'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {message && <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/80 px-3 py-2 text-xs text-slate-400">{message}</div>}
    </div>
  );
}
