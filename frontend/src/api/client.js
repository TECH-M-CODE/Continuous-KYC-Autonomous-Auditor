import axios from 'axios';
import { trace_critical, trace_dismissed } from '../mocks/traces';

export const API_URL = import.meta.env.VITE_API_URL || '/api';

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// For Sprint 2: we will wrap all calls in try/catch and fallback to mock data
// if the backend isn't ready. This ensures the frontend UI can be fully tested.
export const apiClient = {
  getAlerts: async () => {
    try {
      const res = await client.get('/alerts');
      return res.data;
    } catch (e) {
      console.warn("Fallback to mock alerts", e);
      return [
        { id: 'al-101', entity_id: 'ent-881', entity_name: 'Acme Holdings LLC', band: 'critical', score: 85, velocity: 12, event_type: 'adverse_media_fraud', created_at: new Date(Date.now() - 3600000).toISOString() },
        { id: 'al-102', entity_id: 'ent-332', entity_name: 'Stark Industries', band: 'high', score: 65, velocity: 5, event_type: 'transaction_anomaly', created_at: new Date(Date.now() - 7200000).toISOString() },
        { id: 'al-103', entity_id: 'ent-991', entity_name: 'Wayne Enterprises', band: 'medium', score: 45, velocity: 2, event_type: 'sanctions_hit_fuzzy', created_at: new Date(Date.now() - 10800000).toISOString() },
      ];
    }
  },
  
  getEntityTimeline: async (id) => {
    try {
      const res = await client.get(`/entities/${id}`);
      return res.data;
    } catch (e) {
      console.warn("Fallback to mock entity timeline", e);
      return {
        entity: {
          id: id || 'ent-881',
          name: 'Acme Holdings LLC',
          country: 'Cayman Islands',
          sector: 'Financial Services',
          sector_risk: 'High',
          pep_flag: true,
          sanctions_flag: false,
          fatf_country_flag: true,
          current_score: 85,
          watched: true,
        },
        timeline: [
          { id: 'ev-1', type: 'adverse_media', source: 'Reuters', title: 'Acme Holdings named in fraud probe', date: '2026-07-14T10:00:00Z', severity: 'high' },
          { id: 'ev-2', type: 'transaction', source: 'SAML-D', title: 'Large wire transfer to high-risk jurisdiction', amount: '$2,500,000', date: '2026-07-13T14:22:00Z', severity: 'high' },
          { id: 'ev-3', type: 'transaction', source: 'SAML-D', title: 'Structurally anomalous deposits detected', amount: '$9,900 x 5', date: '2026-07-10T09:15:00Z', severity: 'medium' },
        ]
      };
    }
  },

  getTrace: async (eventId) => {
    try {
      const res = await client.get(`/traces/${eventId}`);
      return res.data;
    } catch (e) {
      console.warn("Fallback to mock trace", e);
      // simulate returning critical trace or dismissed trace
      return eventId === 'ev-2' ? trace_dismissed : trace_critical;
    }
  },

  getAudit: async () => {
    try {
      const res = await client.get('/audit');
      return res.data;
    } catch (e) {
      return [
        { id: 'aud-1', seq: 1042, actor: 'System (Resolver)', action: 'ALERT_GENERATED', detail: { alert_id: 'al-101' }, entry_hash: 'e83a9f21...8b', prev_hash: 'f92b1c40...3a', created_at: '2026-07-14T10:15:22Z' },
        { id: 'aud-2', seq: 1043, actor: 'System (Reporter)', action: 'SAR_DRAFTED', detail: { sar_id: 'sar-991' }, entry_hash: 'a1b2c3d4...9f', prev_hash: 'e83a9f21...8b', created_at: '2026-07-14T10:16:05Z' },
      ];
    }
  },

  getWatchlist: async () => {
    try {
      const res = await client.get('/watchlist');
      return res.data;
    } catch (e) {
      return [
        { id: 'ent-881', name: 'Acme Holdings LLC', country: 'Cayman Islands', sector_risk: 'High', score: 85, watched: true },
        { id: 'ent-219', name: 'Globex Corp', country: 'Switzerland', sector_risk: 'Medium', score: 45, watched: true },
        { id: 'ent-332', name: 'Stark Industries', country: 'USA', sector_risk: 'Low', score: 20, watched: false },
        { id: 'ent-991', name: 'Wayne Enterprises', country: 'USA', sector_risk: 'Low', score: 15, watched: false },
      ];
    }
  },

  injectEvent: async (data) => {
    try {
      const res = await client.post('/admin/inject', data);
      return res.data;
    } catch (e) {
      console.warn("Mocking inject event", e);
      return { success: true, injected: data };
    }
  },

  getSAR: async (id) => {
    try {
      const res = await client.get(`/sar/${id}`);
      return res.data;
    } catch (e) {
      console.warn(`Fallback to mock SAR for ${id}`, e);
      return {
        id: id || 'sar-991',
        alert_id: 'al-101',
        entity_id: 'ent-881',
        entity_name: 'Acme Holdings LLC',
        version: 1,
        status: 'pending_review',
        created_at: new Date().toISOString(),
        degraded_draft: false,
        narrative: `This Suspicious Activity Report (SAR) is being filed for Acme Holdings LLC based on a combination of adverse media and structurally anomalous transactions.\n\nOn July 14, 2026, the entity was named in a fraud investigation by Reuters. Shortly after, the entity initiated multiple large wire transfers to high-risk jurisdictions, structured to avoid standard reporting thresholds.\n\nThe combination of events exceeds our critical risk threshold and indicates potential money laundering or sanctions evasion activities.`,
        regulatory_basis: [
          { citation: 'GDPR Article 30', passage: 'Records of processing activities must be maintained.' },
          { citation: 'BSA / AML § 1020.320', passage: 'Reports by banks of suspicious transactions.' }
        ],
        evidence: [
          { source: 'Reuters', snippet: 'Acme Holdings named in fraud probe', relevance: 'High' },
          { source: 'SAML-D', snippet: 'Large wire transfer to high-risk jurisdiction', relevance: 'Critical' }
        ]
      };
    }
  },

  editSAR: async ({ id, narrative }) => {
    try {
      const res = await client.post(`/sar/${id}/edit`, { narrative });
      return res.data;
    } catch (e) {
      console.warn(`Mocking edit SAR ${id}`);
      return { success: true, version: 2, narrative };
    }
  },

  approveSAR: async ({ id, notes }) => {
    try {
      const res = await client.post(`/sar/${id}/approve`, { notes });
      return res.data;
    } catch (e) {
      console.warn(`Mocking approve SAR ${id}`);
      return { success: true, status: 'approved' };
    }
  },

  rejectSAR: async ({ id, notes }) => {
    try {
      const res = await client.post(`/sar/${id}/reject`, { notes });
      return res.data;
    } catch (e) {
      console.warn(`Mocking reject SAR ${id}`);
      return { success: true, status: 'rejected' };
    }
  },

  requestSARInfo: async ({ id, question }) => {
    try {
      const res = await client.post(`/sar/${id}/request-info`, { question });
      return res.data;
    } catch (e) {
      console.warn(`Mocking request info SAR ${id}`);
      return { success: true, status: 'investigating' };
    }
  },

  verifyAuditChain: async () => {
    try {
      const res = await client.get('/audit/verify');
      return res.data;
    } catch (e) {
      console.warn("Mocking verify audit chain");
      return { valid: true, checked: 42, first_bad_seq: null };
    }
  },

  getDrillReport: async () => {
    try {
      const res = await client.get('/drill/latest');
      return res.data;
    } catch (e) {
      console.warn("Mocking get drill report");
      return {
        caught: 17,
        total: 20,
        misses_by_class: {
          'transliteration': 1,
          'shell_name': 2,
          'typo_squat': 0,
          'split_identity': 0
        }
      };
    }
  }
};
