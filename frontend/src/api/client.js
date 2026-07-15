import axios from 'axios';
import { trace_critical, trace_dismissed } from '../mocks/traces';

export const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Unwrap the backend's standard { success, data, message } envelope
// so every call receives the inner `data` payload directly.
client.interceptors.response.use((response) => {
  const body = response.data;
  if (body && typeof body === 'object' && 'success' in body && 'data' in body) {
    response.data = body.data;
  }
  return response;
});

// For Sprint 2: we will wrap all calls in try/catch and fallback to mock data
// if the backend isn't ready. This ensures the frontend UI can be fully tested.
export const apiClient = {
  getAlerts: async () => {
    const res = await client.get('/alerts');
    return res.data?.items || res.data || [];
  },
  
  actionAlert: async ({ id, action, reasoning }) => {
    const res = await client.patch(`/alerts/${id}/action`, { action, reasoning });
    return res.data;
  },

  getEntityTimeline: async (id) => {
    const res = await client.get(`/entities/${id}`);
    return res.data;
  },

  getTrace: async (alertId) => {
    const res = await client.get(`/alerts/${alertId}`);
    return res.data?.trace;
  },

  getAudit: async (entityId = 'ent-881') => {
    const res = await client.get(`/audit/${entityId}`);
    return res.data?.items || res.data || [];
  },

  getWatchlist: async () => {
    const res = await client.get('/entities');
    return res.data?.items || res.data || [];
  },

  injectEvent: async (data) => {
    const res = await client.post('/admin/inject', data);
    return res.data;
  },

  getSAR: async (id) => {
    const res = await client.get(`/sars/${id}`);
    return res.data;
  },

  editSAR: async ({ id, narrative, citations }) => {
    const res = await client.put(`/sars/${id}`, { narrative, citations: citations || [] });
    return res.data;
  },

  approveSAR: async ({ id, comments }) => {
    const res = await client.post(`/sars/${id}/decision`, { decision: 'APPROVE', comments });
    return res.data;
  },

  rejectSAR: async ({ id, comments }) => {
    const res = await client.post(`/sars/${id}/decision`, { decision: 'REJECT', comments });
    return res.data;
  },

  requestSARInfo: async ({ id, question }) => {
    const res = await client.post(`/sars/${id}/request-info`, { question });
    return res.data;
  },

  verifyAuditChain: async () => {
    const res = await client.get('/audit/verify');
    return res.data;
  },

  getDrillReport: async () => {
    const res = await client.get('/drill/latest');
    return res.data;
  }
};
