import { USE_MOCK } from './client';
import { mockApi } from './mock';
import { backend } from './backend';
import { mockExtra } from './mockExtra';

// Real backend: GET /patients, /patients/{id}, /patients/{id}/readings?from=, /patients/{id}/risk-score (see api/backend.js).
const api = USE_MOCK ? { ...mockApi, ...mockExtra } : backend;

export const patientsApi = {
  getAll: () => api.patients(),
  getById: (id) => api.patient(id),
  getReadings: (id) => api.readings(id),
  getRiskScore: (id) => api.risk(id),
  getAllWithStatus: () => api.patientsAll(),
  create: (body) => api.createPatient(body),
  getAttention: () => api.attention(),
};
