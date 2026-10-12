import { create } from 'zustand';
import { authApi } from '../api/auth';

export const useAuthStore = create((set) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),
  login: async (username, password) => {
    const { data } = await authApi.login(username, password);
    localStorage.setItem('access_token', data.access_token);
    set({ token: data.access_token, isAuthenticated: true });
    const me = await authApi.me();
    set({ user: me.data });
    return me.data;
  },
  logout: () => {
    localStorage.removeItem('access_token');
    set({ user: null, token: null, isAuthenticated: false });
  },
  fetchMe: async () => {
    const { data } = await authApi.me();
    set({ user: data });
  },
}));
