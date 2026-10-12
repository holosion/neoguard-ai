import client from './client';
import { backend } from './backend';

export const authApi = {
  login: (username, password) => client.post('/auth/login', new URLSearchParams({ username, password })),
  me: () => backend.me(),
  requestAccess: (body) => backend.requestAccess(body),
  clinics: () => backend.clinics(),
};
