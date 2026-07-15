import React, { useCallback, useMemo, useState, useEffect } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Panel,
  MarkerType,
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

  // Nodes have a fixed width/height roughly matching the Tailwind classes (w-72 is 288px)
  const nodeWidth = 288;
  const nodeHeight = 100;

  dagreGraph.setGraph({ rankdir: direction, ranksep: 80, nodesep: 100 });

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
    animated: true, // Always animate for a nice flow effect
    style: { stroke: '#475569', strokeWidth: 2, opacity: 0.7 },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#475569',
    },
    labelStyle: { fill: '#38bdf8', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' },
    labelBgStyle: { fill: '#0f172a', fillOpacity: 0.9, stroke: '#1e293b', strokeWidth: 1, rx: 6, ry: 6 },
    labelBgPadding: [8, 4],
    labelShowBg: true
  })), [trace]);

  const [layoutDirection, setLayoutDirection] = useState('LR');

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => getLayoutedElements(initialNodes, initialEdges, layoutDirection),
    [initialNodes, initialEdges, layoutDirection]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  useEffect(() => {
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

  const onNodeClick = useCallback((_, node) => {
    setSelectedNode(node);
  }, []);

  return (
    <div className="flex h-full w-full relative bg-slate-950 overflow-hidden">
      {/* Background Gradient Effect */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-slate-950 opacity-80 pointer-events-none" />
      
      <div className="flex-1 relative z-0">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ nodes: [{ id: trace.nodes[0]?.id }], maxZoom: 1.1, padding: 0.5 }}
          minZoom={0.2}
          maxZoom={1.5}
          className="bg-transparent"
        >
          <Background color="#334155" gap={24} size={2} className="opacity-40" />
          <Controls className="bg-slate-800/80 backdrop-blur border-slate-700 fill-slate-300 shadow-xl rounded-xl overflow-hidden" />
          <MiniMap
            nodeColor={(n) => {
              if (n.type === 'event') return '#3b82f6';
              if (n.type === 'screen') return '#a855f7';
              if (n.type === 'verify') return '#10b981';
              if (n.type === 'score') return '#f97316';
              if (n.type === 'propagate') return '#06b6d4';
              if (n.type === 'decision') return n.data.label?.toLowerCase().includes('alert') ? '#ef4444' : '#64748b';
              return '#64748b';
            }}
            maskColor="rgba(15, 23, 42, 0.6)"
            className="bg-slate-900/80 border border-slate-700/50 rounded-xl overflow-hidden shadow-2xl backdrop-blur-md"
          />

          <Panel position="top-right" className="m-4">
            <button
              onClick={() => setLayoutDirection(prev => prev === 'LR' ? 'TB' : 'LR')}
              className="px-4 py-2 bg-slate-800/80 hover:bg-slate-700 backdrop-blur-md border border-slate-600/50 rounded-xl text-xs uppercase tracking-wider font-bold text-slate-200 transition-all shadow-lg"
            >
              {layoutDirection === 'LR' ? 'Switch to Vertical' : 'Switch to Horizontal'}
            </button>
          </Panel>

          {trace.counterfactual && (
            <Panel position="bottom-center" className="mb-8">
              <div className="bg-slate-900/80 backdrop-blur-md border border-brand-500/30 text-slate-300 px-6 py-4 rounded-2xl shadow-2xl shadow-brand-500/10 max-w-2xl text-sm flex items-start gap-4">
                <div className="p-2 bg-brand-500/10 rounded-xl shrink-0">
                  <Info className="w-5 h-5 text-brand-400" />
                </div>
                <div className="pt-0.5 leading-relaxed">
                  <span className="font-bold text-brand-300 uppercase text-xs tracking-wider block mb-1">Counterfactual Analysis</span>
                  {trace.counterfactual}
                </div>
              </div>
            </Panel>
          )}
        </ReactFlow>
      </div>

      {/* Side Drawer for Node Details */}
      {selectedNode && (
        <div className="w-[420px] border-l border-slate-800/60 bg-slate-900/80 backdrop-blur-2xl p-6 overflow-y-auto flex flex-col shadow-2xl z-10 animate-in slide-in-from-right duration-300 relative">
          <div className="flex justify-between items-start mb-8">
            <div>
              <div className="text-xs font-bold uppercase tracking-widest text-brand-400 mb-2">{selectedNode.data.kind}</div>
              <h3 className="text-xl font-bold text-slate-100 leading-tight">{selectedNode.data.label}</h3>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-slate-500 hover:text-white p-2 bg-slate-800/50 hover:bg-slate-700/50 rounded-full transition-all"
            >
              ×
            </button>
          </div>

          <div className="bg-slate-950/50 p-5 rounded-2xl mb-8 border border-slate-800/60 shadow-inner">
            <h4 className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-brand-500"></div>
              Narrative Detail
            </h4>
            <p className="text-sm text-slate-300 leading-relaxed font-medium">{selectedNode.data.detail}</p>
          </div>

          <div>
            <h4 className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
              Computed Values
            </h4>
            <div className="bg-slate-950/50 rounded-2xl overflow-hidden border border-slate-800/60 shadow-inner">
              <table className="w-full text-sm text-left">
                <tbody>
                  {Object.entries(selectedNode.data.values || {}).map(([k, v], idx) => (
                    <tr key={k} className={idx !== 0 ? 'border-t border-slate-800/60' : ''}>
                      <td className="px-5 py-4 font-semibold text-slate-400 bg-slate-900/30 w-2/5 border-r border-slate-800/30">{k}</td>
                      <td className="px-5 py-4 text-slate-200 font-mono text-xs break-all">
                        {typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}
                      </td>
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
