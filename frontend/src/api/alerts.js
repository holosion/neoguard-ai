import { backend } from './backend';

export const alertsApi = {
  getAll: (params) => backend.alerts(params),
  acknowledge: (id) => backend.acknowledge(id),
};
