import axios from 'axios';
import { dashboardPreview } from '../utils/preview';

const client = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1' });

client.interceptors.request.use((config) => {
  if (dashboardPreview) {
    config.adapter = async () => {
      if (config.method !== 'get') throw new Error('Changes are unavailable in dashboard preview.');
      const data = config.url === '/admin/overview'
        ? { devices: { online_recently: 0, active: 0 }, active_sessions: 0, sync_lag_seconds: null }
        : [];
      return { data, status: 200, statusText: 'OK', headers: {}, config };
    };
    return config;
  }
  const token = sessionStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!dashboardPreview && error.response?.status === 401) {
      sessionStorage.removeItem('access_token');
      sessionStorage.removeItem('user');
      sessionStorage.removeItem('must_change_password');
      window.location.href = '/login?expired=1';
    }
    return Promise.reject(error);
  }
);

export default client;
