import { backend } from './backend';

export const sessionsApi = {
  list: () => backend.sessions(),
  start: (body) => backend.startSession(body),
  stop: (id) => backend.stopSession(id),
  availableDevices: () => backend.availableDevices(),
};

export const devicesApi = { list: () => backend.devicesBasic() };
