import { create } from 'zustand';
import { authApi } from '../api/auth';
import { useAlertStore } from './alertStore';

export const useAuthStore = create((set) => ({
  user: null,
  token: sessionStorage.getItem('access_token'),
  isAuthenticated: !!sessionStorage.getItem('access_token'),
  login: async (username, password) => {
    const { data } = await authApi.login(username, password);
    sessionStorage.setItem('access_token', data.access_token);
    set({ token: data.access_token, isAuthenticated: true });
    const me = await authApi.me();
    set({ user: me.data });
    return me.data;
  },
  logout: () => {
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('user');
    useAlertStore.getState().clear();
    set({ user: null, token: null, isAuthenticated: false });
  },
  fetchMe: async () => {
    const { data } = await authApi.me();
    set({ user: data });
  },
}));
