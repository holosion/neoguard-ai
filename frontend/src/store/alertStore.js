import { create } from 'zustand';
import { alertsApi } from '../api/alerts';

export const useAlertStore = create((set, get) => ({
  alerts: [],
  loading: true,
  error: null,
  clear: () => set({ alerts: [], loading: true, error: null }),
  refresh: async () => {
    try {
      const { data } = await alertsApi.getAll();
      set({ alerts: data, error: null, loading: false });
    } catch (e) {
      set({ error: e, loading: false });
    }
  },
  // Throws on failure so the button that called it can show an error.
  acknowledge: async (id) => {
    await alertsApi.acknowledge(id);
    set((s) => ({
      alerts: s.alerts.map((a) => (a.id === id ? { ...a, acknowledged_at: new Date().toISOString(), acknowledged_by: 'You' } : a)),
    }));
    get().refresh();
  },
}));

export const selectUnacknowledged = (s) => s.alerts.filter((a) => !a.acknowledged_at).length;
