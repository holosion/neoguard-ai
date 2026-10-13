import { create } from 'zustand';
import { authApi } from '../api/auth';
import { useAlertStore } from './alertStore';

export const useAuthStore = create((set) => ({
  user: null,
  token: sessionStorage.getItem('access_token'),
  isAuthenticated: !!sessionStorage.getItem('access_token'),
  mustChangePassword: sessionStorage.getItem('must_change_password') === 'true',
  login: async (username, password) => {
    const { data } = await authApi.login(username, password);
    sessionStorage.setItem('access_token', data.access_token);
    sessionStorage.setItem('must_change_password', String(data.must_change_password));
    if (data.must_change_password) {
      const user = { role: data.role };
      set({ token: data.access_token, isAuthenticated: true, mustChangePassword: true, user });
      return { ...user, must_change_password: true };
    }
    set({ token: data.access_token, isAuthenticated: true, mustChangePassword: false });
    const me = await authApi.me();
    set({ user: me.data });
    return me.data;
  },
  changePassword: async (old_password, new_password) => {
    const { data } = await authApi.changePassword({ old_password, new_password });
    sessionStorage.setItem('access_token', data.access_token);
    sessionStorage.setItem('must_change_password', 'false');
    set({ token: data.access_token, mustChangePassword: false });
    const me = await authApi.me();
    set({ user: me.data, isAuthenticated: true });
    return me.data;
  },
  logout: () => {
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('user');
    sessionStorage.removeItem('must_change_password');
    useAlertStore.getState().clear();
    set({ user: null, token: null, isAuthenticated: false, mustChangePassword: false });
  },
  fetchMe: async () => {
    const { data } = await authApi.me();
    set({ user: data });
  },
}));
