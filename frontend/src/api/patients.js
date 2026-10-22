import { backend } from './backend';

export const patientsApi = {
  getAll: () => backend.patients(),
  getById: (id) => backend.patient(id),
  getReadings: (id) => backend.readings(id),
  getRiskScore: (id) => backend.risk(id),
  getAllWithStatus: () => backend.patientsAll(),
  create: (body) => backend.createPatient(body),
  getAttention: () => backend.attention(),
};
