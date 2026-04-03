// News store using Zustand
import { create } from 'zustand';
import { newsApi } from '../services/api';
import { DEFAULT_RECENT_HOURS } from '../utils/timeUtils';
import type { NewsEvent, PaginatedResponse } from '../types/news';

interface NewsState {
  // State
  events: NewsEvent[];
  selectedEvent: NewsEvent | null;
  isLoading: boolean;
  error: string | null;
  total: number;
  page: number;
  pageSize: number;

  // Actions
  fetchHotEvents: (params?: { page?: number; page_size?: number; scope?: string; category?: string }) => Promise<void>;
  setSelectedEvent: (event: NewsEvent | null) => void;
  clearError: () => void;
}

export const useNewsStore = create<NewsState>((set, get) => ({
  // Initial state
  events: [],
  selectedEvent: null,
  isLoading: false,
  error: null,
  total: 0,
  page: 1,
  pageSize: 500,

  // Actions
  fetchHotEvents: async (params = {}) => {
    set({ isLoading: true, error: null });

    try {
      const page = params.page ?? get().page;
      const pageSize = params.page_size ?? get().pageSize;

      const response = await newsApi.getHotNews({
        page,
        page_size: pageSize,
        since_hours: DEFAULT_RECENT_HOURS,
        ...params,
      });

      const data = response as unknown as PaginatedResponse<NewsEvent>;

      set({
        events: data.items,
        total: data.total,
        page: data.page,
        isLoading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch news',
        isLoading: false,
      });
    }
  },

  setSelectedEvent: (event) => {
    set({ selectedEvent: event });
  },

  clearError: () => {
    set({ error: null });
  },
}));
