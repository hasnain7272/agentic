import { useCallback } from 'react';
import { ReactFlow, MiniMap, Controls, Background, useNodesState, useEdgesState, addEdge, type Connection, type Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

const initialNodes = [
  { id: 'master', position: { x: 250, y: 50 }, data: { label: 'Master Coordinator' }, type: 'input' },
  { id: 'worker-1', position: { x: 100, y: 200 }, data: { label: 'Code Execution Engine' } },
  { id: 'worker-2', position: { x: 400, y: 200 }, data: { label: 'Filesystem Operator' } },
];
const initialEdges = [{ id: 'e1-2', source: 'master', target: 'worker-1', animated: true }];

export function SwarmTopology() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection | Edge) => setEdges((eds) => addEdge({ ...params, animated: true }, eds)),
    [setEdges],
  );

  return (
    <div className="h-full w-full bg-slate-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        colorMode="dark"
        fitView
      >
        <Controls />
        <MiniMap nodeColor="#3b82f6" maskColor="rgba(0,0,0, 0.4)" />
        <Background color="#1e293b" gap={16} />
      </ReactFlow>
    </div>
  );
}
