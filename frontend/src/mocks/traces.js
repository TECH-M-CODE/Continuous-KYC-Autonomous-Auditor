export const trace_critical = {
  trace_id: "tr-001",
  event_id: "ev-1",
  entity_id: "ent-881",
  final_outcome: "alert_critical",
  counterfactual: null,
  created_at: new Date().toISOString(),
  nodes: [
    {
      id: "n1",
      kind: "event",
      label: "Adverse Media",
      detail: "Reuters published article: 'Acme Holdings named in fraud probe'",
      values: { source: "Reuters", type: "adverse_media" },
      outcome: "pass"
    },
    {
      id: "n2",
      kind: "screen",
      label: "Fuzzy Match: 95",
      detail: "Name 'Acme Holdings' matched watchlist 'Acme Holdings LLC' at token_set_ratio 95",
      values: { token_set_ratio: 95 },
      outcome: "pass"
    },
    {
      id: "n3",
      kind: "verify",
      label: "Confidence: 0.92",
      detail: "Source 'Reuters' has credibility 0.9. Event matched historical transaction anomalies.",
      values: { credibility: 0.9, corroboration_boost: 0.1, final_confidence: 0.92 },
      outcome: "pass"
    },
    {
      id: "n4",
      kind: "score",
      label: "Score Delta: +15.6",
      detail: "adverse_media (weight 12) × severity 1.0 × jurisdiction 1.3 = +15.6",
      values: { weight: 12, severity: 1.0, jurisdiction_factor: 1.3, delta: 15.6 },
      outcome: "pass"
    },
    {
      id: "n5",
      kind: "propagate",
      label: "Propagate to Directors",
      detail: "Passed delta to 2 related entity_persons",
      values: { propagation_factor: 0.35, hops: 1 },
      outcome: "pass"
    },
    {
      id: "n6",
      kind: "decision",
      label: "Critical Alert",
      detail: "Entity score reached 85 (Critical band ≥ 80)",
      values: { total_score: 85, band_threshold: 80 },
      outcome: null
    }
  ],
  edges: [
    { source: "n1", target: "n2", label: "extracted entity" },
    { source: "n2", target: "n3", label: "match > 80" },
    { source: "n3", target: "n4", label: "conf > 0.75" },
    { source: "n4", target: "n5", label: "update entities" },
    { source: "n4", target: "n6", label: "evaluate bands" }
  ]
};

export const trace_dismissed = {
  trace_id: "tr-002",
  event_id: "ev-2",
  entity_id: "ent-991",
  final_outcome: "dismissed",
  counterfactual: "Would have proceeded if: source credibility ≥ 0.7 (was 0.4, single uncorroborated blog) or fuzzy match ≥ 80 (was 64).",
  created_at: new Date().toISOString(),
  nodes: [
    {
      id: "n1",
      kind: "event",
      label: "Blog Post",
      detail: "Unknown RSS feed: 'Wayne Ent might be risky'",
      values: { source: "unknown_rss", type: "adverse_media" },
      outcome: "pass"
    },
    {
      id: "n2",
      kind: "screen",
      label: "Fuzzy Match: 64",
      detail: "Name 'Wayne Ent' matched watchlist 'Wayne Enterprises' at token_set_ratio 64",
      values: { token_set_ratio: 64 },
      outcome: "pass"
    },
    {
      id: "n3",
      kind: "verify",
      label: "Confidence: 0.25",
      detail: "Source 'unknown_rss' has credibility 0.4. No corroboration.",
      values: { credibility: 0.4, corroboration_boost: 0, final_confidence: 0.25 },
      outcome: "fail"
    },
    {
      id: "n4",
      kind: "decision",
      label: "Dismissed",
      detail: "Confidence 0.25 is below dismissal threshold of 0.40",
      values: { confidence: 0.25, threshold: 0.40 },
      outcome: null
    }
  ],
  edges: [
    { source: "n1", target: "n2", label: "extracted entity" },
    { source: "n2", target: "n3", label: "match < 80" },
    { source: "n3", target: "n4", label: "conf < 0.40" }
  ]
};
