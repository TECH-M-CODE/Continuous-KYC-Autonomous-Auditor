export const API_URL = import.meta.env.VITE_API_URL || '/api';

export const apiClient = {
  get: async (endpoint) => {
    const res = await fetch(`${API_URL}${endpoint}`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return res.json();
  },
  post: async (endpoint, data) => {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return res.json();
  }
};
