import axios from 'axios';

const client = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1' });

client.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem('access_token');
      sessionStorage.removeItem('user');
      window.location.href = '/login?expired=1';
    }
    return Promise.reject(error);
  }
);

export default client;
