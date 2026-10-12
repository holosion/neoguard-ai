import { USE_MOCK } from './client';
import { mockAdminApi } from './mockAdmin';
import { backend } from './backend';

const api = USE_MOCK ? mockAdminApi : backend;

// Real backend routes used: GET /admin/overview, GET /admin/device-health, GET/POST /devices, GET/PATCH /devices/{id},
// POST /sessions, GET /patients, POST /auth/users. Approvals need GET /auth/users and PATCH /auth/users/{id} (not built yet).
export const adminApi = {
  overview: () => api.overview(),
  getDevices: () => api.devices(),
  getDevice: (id) => api.device(id),
  registerDevice: (body) => api.registerDevice(body),
  updateDevice: (id, body) => api.updateDevice(id, body),
  decommissionDevice: (id) => api.decommission(id),
  getUnassignedPatients: () => api.unassignedPatients(),
  assignDevice: (id, body) => api.assign(id, body),
  getUsers: () => api.users(),
  userAction: (id, action) => api.userAction(id, action),
  createUser: (body) => api.createUser(body),
};
