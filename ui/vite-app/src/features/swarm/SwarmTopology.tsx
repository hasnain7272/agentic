import { useCallback, useEffect, useState } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { apiClient } from '@/api/client';
import { useToastStore } from '@/components/Toast';
import { Loader2, Network } from 'lucide-react';

interface SessionItem {
  id: string;
  name: string;
  model: string;
  a2a_links?: string[];
}

export function SwarmTopology() {
  const addToast = useToastStore((s) => s.addToast);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading] = useState(false);

  const fetchTopology = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<{ sessions: SessionItem[] }>('/sessions/');
      const sessions = res.data?.sessions || [];

      // Calculate node layout (simple circle layout)
      const radius = 180;
      const centerX = 400;
      const centerY = 250;

      const newNodes: Node[] = sessions.map((s, index) => {
        const angle = (index / Math.max(sessions.length, 1)) * 2 * Math.PI;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);

        return {
          id: s.id,
          position: { x, y },
          data: { label: `${s.name || s.id.slice(0, 8)} (${s.model})` },
          style: {
            background: '#0f0f11',
            color: '#f8fafc',
            border: '1px solid #1e293b',
            borderRadius: '12px',
            fontSize: '11px',
            fontWeight: '600',
            padding: '10px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
            width: 150,
            textAlign: 'center',
          },
        };
      });

      const newEdges: Edge[] = [];
      sessions.forEach((s) => {
        if (s.a2a_links) {
          s.a2a_links.forEach((targetId) => {
            // Check if target node exists to avoid drawing dead edges
            if (sessions.some((session) => session.id === targetId)) {
              newEdges.push({
                id: `edge-${s.id}-${targetId}`,
                source: s.id,
                target: targetId,
                animated: true,
                style: { stroke: '#10b981', strokeWidth: 2 },
              });
            }
          });
        }
      });

      setNodes(newNodes);
      setEdges(newEdges);
    } catch (e) {
      console.error('Failed to fetch Swarm topology', e);
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => {
    fetchTopology();
  }, [fetchTopology]);

  const onConnect = useCallback(
    async (params: Connection) => {
      if (!params.source || !params.target) return;
      if (params.source === params.target) {
        addToast('error', 'Cannot link a session to itself.');
        return;
      }

      try {
        await apiClient.post(`/sessions/${params.source}/link`, {
          target_session_id: params.target,
        });
        addToast('success', 'Agent-to-Agent session link created!');
        setEdges((eds) => addEdge({ ...params, animated: true, style: { stroke: '#10b981', strokeWidth: 2 } }, eds));
        fetchTopology();
      } catch (err: any) {
        addToast('error', err.message || 'Failed to connect sessions.');
      }
    },
    [setEdges, addToast, fetchTopology]
  );

  const onEdgesDelete = useCallback(
    async (edgesToDelete: Edge[]) => {
      for (const edge of edgesToDelete) {
        try {
          await apiClient.delete(`/sessions/${edge.source}/link/${edge.target}`);
          addToast('success', 'Session link removed.');
        } catch (err: any) {
          addToast('error', err.message || 'Failed to remove session link.');
        }
      }
      fetchTopology();
    },
    [addToast, fetchTopology]
  );

  return (
    <div className="h-full w-full bg-[#0c0c0c] flex flex-col">
      <div className="flex items-center justify-between border-b border-slate-800 px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-emerald-500/10 p-1.5 text-emerald-400">
            <Network className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white">Agent Swarm Mesh (A2A)</h2>
            <p className="text-[11px] text-slate-500">Connect agent sessions together by dragging links between them. Select edges and press Delete to unlink.</p>
          </div>
        </div>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />}
      </div>

      <div className="flex-1 min-h-0 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onEdgesDelete={onEdgesDelete}
          colorMode="dark"
          fitView
        >
          <Controls />
          <MiniMap nodeColor="#10b981" maskColor="rgba(0,0,0, 0.6)" />
          <Background color="#1e293b" gap={16} />
        </ReactFlow>
      </div>
    </div>
  );
}
