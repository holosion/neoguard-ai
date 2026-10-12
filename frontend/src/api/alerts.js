import { USE_MOCK } from './client';
import { mockApi } from './mock';
import { backend } from './backend';

const api = USE_MOCK ? mockApi : backend;

// GET /alerts and POST /alerts/{id}/acknowledge on the real backend.
export const alertsApi = {
  getAll: (params) => api.alerts(params),
  acknowledge: (id) => api.acknowledge(id),
};
