import { backend } from './backend';

export const adminApi = {
  overview: () => backend.overview(),
  getDevices: () => backend.devices(),
  getDevice: (id) => backend.device(id),
  registerDevice: (body) => backend.registerDevice(body),
  updateDevice: (id, body) => backend.updateDevice(id, body),
  decommissionDevice: (id) => backend.decommission(id),
  getUnassignedPatients: () => backend.unassignedPatients(),
  assignDevice: (id, body) => backend.assign(id, body),
  getUsers: () => backend.users(),
  userAction: (id, active) => backend.userAction(id, active),
  createUser: (body) => backend.createUser(body),
  getAccessRequests: () => backend.accessRequests(),
  decideAccessRequest: (id, body) => backend.decideAccessRequest(id, body),
  getClinics: () => backend.clinics(),
  createClinic: (body) => backend.createClinic(body),
  getThresholds: () => backend.thresholds(),
};
