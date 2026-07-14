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
    <div className="flex h-full w-full relative bg-slate-950">
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
          className="bg-slate-950"
        >
          <Background color="#1e293b" gap={16} />
          <Controls className="bg-slate-800 border-slate-700 fill-slate-300" />
          
          {trace.counterfactual && (
            <Panel position="bottom-center" className="mb-4">
              <div className="bg-slate-800 border border-slate-700 text-slate-300 px-6 py-3 rounded-lg shadow-xl max-w-2xl text-sm flex items-start gap-3">
                <Info className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-200">Counterfactual: </span>
                  {trace.counterfactual}
                </div>
              </div>
            </Panel>
          )}
        </ReactFlow>
      </div>

      {/* Side Drawer for Node Details */}
      {selectedNode && (
        <div className="w-96 border-l border-slate-800 bg-slate-900 p-6 overflow-y-auto flex flex-col shadow-2xl z-10 animate-in slide-in-from-right duration-200">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-semibold text-slate-100">{selectedNode.data.label}</h3>
            <button 
              onClick={() => setSelectedNode(null)}
              className="text-slate-400 hover:text-slate-200 p-1"
            >
              ×
            </button>
          </div>
          
          <div className="bg-slate-800/50 p-4 rounded-lg mb-6 border border-slate-800">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Narrative Detail</h4>
            <p className="text-sm text-slate-200 leading-relaxed">{selectedNode.data.detail}</p>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Computed Values</h4>
            <div className="bg-slate-950 rounded-lg overflow-hidden border border-slate-800">
              <table className="w-full text-sm text-left">
                <tbody>
                  {Object.entries(selectedNode.data.values || {}).map(([k, v], idx) => (
                    <tr key={k} className={idx !== 0 ? 'border-t border-slate-800' : ''}>
                      <td className="px-4 py-3 font-medium text-slate-400 bg-slate-900/50 w-1/2">{k}</td>
                      <td className="px-4 py-3 text-slate-200">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</td>
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
