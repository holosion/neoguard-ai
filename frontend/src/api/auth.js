import client, { USE_MOCK } from './client';
import { mockApi } from './mock';
import { mockAdminApi } from './mockAdmin';
import { backend } from './backend';

export const authApi = {
  login: async (username, password) => {
    if (USE_MOCK) {
      const res = await mockApi.login(username);
      localStorage.setItem('mock_role', res.data.role);
      return res;
    }
    // FastAPI's OAuth2 password flow expects form-encoded fields. `username` may be a username or an email.
    return client.post('/auth/login', new URLSearchParams({ username, password }));
  },
  me: () => (USE_MOCK ? mockApi.me() : backend.me()),
  // POST /auth/request-access is not in the backend yet. See the README.
  requestAccess: (body) => (USE_MOCK ? mockAdminApi.requestAccess() : backend.requestAccess(body)),
};
