import uuid
from datetime import datetime, timezone
from app.schemas.traces import TraceNode, TraceEdge, DecisionTrace

class TraceBuilder:
    def __init__(self, event_id: str, entity_id: str = None):
        self.trace_id = str(uuid.uuid4())
        self.event_id = event_id
        self.entity_id = entity_id
        self.nodes = []
        self.edges = []
        self._last_node_id = None
        
    def add(self, kind: str, label: str, detail: str, values: dict, outcome: str = None):
        node_id = f"node_{len(self.nodes)}"
        node = TraceNode(
            id=node_id,
            kind=kind,
            label=label,
            detail=detail,
            values=values,
            outcome=outcome
        )
        self.nodes.append(node)
        
        # Auto-generate sequential edges
        if self._last_node_id:
            edge = TraceEdge(source=self._last_node_id, target=node_id)
            self.edges.append(edge)
            
        self._last_node_id = node_id
        return node_id
        
    def add_edge(self, source: str, target: str, label: str = None):
        self.edges.append(TraceEdge(source=source, target=target, label=label))
        
    def finalize(self, final_outcome: str, counterfactual: str = None) -> DecisionTrace:
        return DecisionTrace(
            trace_id=self.trace_id,
            event_id=self.event_id,
            entity_id=self.entity_id,
            final_outcome=final_outcome,
            counterfactual=counterfactual,
            nodes=self.nodes,
            edges=self.edges,
            created_at=datetime.now(timezone.utc)
        )