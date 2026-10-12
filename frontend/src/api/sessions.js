import { USE_MOCK } from './client';
import { mockApi } from './mock';
import { mockExtra } from './mockExtra';
import { backend } from './backend';

const api = USE_MOCK ? { ...mockApi, ...mockExtra } : backend;

// Real backend: GET /sessions, POST /sessions { patient_id, device_id }, POST /sessions/{id}/stop, GET /devices.
// The backend starts a session at the current time.
export const sessionsApi = {
  list: () => api.sessions(),
  start: (body) => api.startSession(body),
  stop: (id) => api.stopSession(id),
  availableDevices: () => api.availableDevices(),
};

export const devicesApi = { list: () => api.devicesBasic() };
