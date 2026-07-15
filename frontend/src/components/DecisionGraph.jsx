import React, { useCallback, useMemo, useState } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { EventNode, ScreenNode, VerifyNode, ScoreNode, PropagateNode, DecisionNode } from './TraceNode';
import { Info } from 'lucide-react';

const nodeTypes = {
  event: EventNode,
  screen: ScreenNode,
  verify: VerifyNode,
  score: ScoreNode,
  propagate: PropagateNode,
  decision: DecisionNode,
};

const getLayoutedElements = (nodes, edges, direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  // Nodes have a fixed width/height roughly matching the Tailwind classes
  const nodeWidth = 260; 
  const nodeHeight = 80;

  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = direction === 'LR' ? 'left' : 'top';
    node.sourcePosition = direction === 'LR' ? 'right' : 'bottom';
    // Shift slightly to center
    node.position = {
      x: nodeWithPosition.x - nodeWidth / 2,
      y: nodeWithPosition.y - nodeHeight / 2,
    };
  });

  return { nodes, edges };
};

export const DecisionGraph = ({ trace }) => {
  const [selectedNode, setSelectedNode] = useState(null);

  const initialNodes = useMemo(() => trace.nodes.map(n => ({
    id: n.id,
    type: n.kind, // Matches nodeTypes keys
    data: { kind: n.kind, label: n.label, detail: n.detail, values: n.values },
    position: { x: 0, y: 0 } // Computed by dagre
  })), [trace]);

  const initialEdges = useMemo(() => trace.edges.map((e, idx) => ({
    id: `e-${idx}`,
    source: e.source,
    target: e.target,
    label: e.label,
    animated: e.label?.includes('update') || e.label?.includes('evaluate'),
    style: { stroke: '#475569', strokeWidth: 2 },
    labelStyle: { fill: '#94a3b8', fontWeight: 500 },
    labelBgStyle: { fill: '#0f172a' }
  })), [trace]);

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => getLayoutedElements(initialNodes, initialEdges),
    [initialNodes, initialEdges]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  const onNodeClick = useCallback((_, node) => {
    setSelectedNode(node);
  }, []);

  return (
    <div className="flex h-full w-full relative bg-transparent">
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.5}
          maxZoom={1.5}
          className="bg-transparent"
        >
          <Background color="#cbd5e1" gap={16} />
          <Controls className="!bg-white/80 !border-white/60 !fill-slate-600 shadow-sm backdrop-blur-md" />
          
          {trace.counterfactual && (
            <Panel position="bottom-center" className="mb-4">
              <div className="glass-panel px-6 py-4 shadow-xl max-w-2xl text-sm flex items-start gap-3">
                <Info className="w-5 h-5 text-brand-500 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-slate-800">Counterfactual: </span>
                  <span className="text-slate-600 font-medium">{trace.counterfactual}</span>
                </div>
              </div>
            </Panel>
          )}
        </ReactFlow>
      </div>

      {/* Side Drawer for Node Details */}
      {selectedNode && (
        <div className="w-96 border-l border-white/50 glass-panel !rounded-none !border-y-0 !border-r-0 p-6 overflow-y-auto flex flex-col shadow-2xl z-10 animate-in slide-in-from-right duration-200">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-bold text-slate-800 drop-shadow-sm">{selectedNode.data.label}</h3>
            <button 
              onClick={() => setSelectedNode(null)}
              className="text-slate-400 hover:text-slate-600 bg-white/40 hover:bg-white/60 p-1.5 rounded-full transition-colors"
            >
              ×
            </button>
          </div>
          
          <div className="bg-white/40 p-5 rounded-xl mb-6 border border-white/60 shadow-inner">
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Narrative Detail</h4>
            <p className="text-sm text-slate-700 leading-relaxed font-medium">{selectedNode.data.detail}</p>
          </div>

          <div>
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Computed Values</h4>
            <div className="bg-white/50 rounded-xl overflow-hidden border border-white/60 shadow-inner">
              <table className="w-full text-sm text-left">
                <tbody>
                  {Object.entries(selectedNode.data.values || {}).map(([k, v], idx) => (
                    <tr key={k} className={idx !== 0 ? 'border-t border-white/40' : ''}>
                      <td className="px-4 py-3 font-bold text-slate-600 bg-white/40 w-1/2">{k}</td>
                      <td className="px-4 py-3 text-slate-800 font-medium">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
