// News store using Zustand
import { create } from 'zustand';
import { newsApi } from '../services/api';
import { DEFAULT_RECENT_HOURS } from '../utils/timeUtils';
import type { NewsEvent, PaginatedResponse, SourceTier } from '../types/news';

interface NewsState {
  // State
  events: NewsEvent[];
  selectedEvent: NewsEvent | null;
  selectedTags: string[];
  selectedSourceTier: SourceTier | null;
  isLoading: boolean;
  error: string | null;
  total: number;
  page: number;
  pageSize: number;

  // Actions
  fetchHotEvents: (params?: {
    page?: number;
    page_size?: number;
    scope?: string;
    category?: string;
    tag?: string;
    tags_any?: string;
    tags_all?: string;
    source_tier?: SourceTier;
  }) => Promise<void>;
  setSelectedEvent: (event: NewsEvent | null) => void;
  toggleTag: (tag: string) => string[];
  clearTags: () => void;
  setSourceTier: (tier: SourceTier | null) => void;
  clearError: () => void;
}

export const useNewsStore = create<NewsState>((set, get) => ({
  // Initial state
  events: [],
  selectedEvent: null,
  selectedTags: [],
  selectedSourceTier: null,
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
      const selectedTags = get().selectedTags;
      const selectedSourceTier = get().selectedSourceTier;
      const tagParams = params.tags_any !== undefined
        ? {}
        : (selectedTags.length > 0 ? { tags_any: selectedTags.join(',') } : {});
      const sourceTierParams = params.source_tier !== undefined
        ? {}
        : (selectedSourceTier ? { source_tier: selectedSourceTier } : {});

      const response = await newsApi.getHotNews({
        page,
        page_size: pageSize,
        since_hours: DEFAULT_RECENT_HOURS,
        ...tagParams,
        ...sourceTierParams,
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

  toggleTag: (tag) => {
    const normalized = tag.trim().toLowerCase();
    if (!normalized) {
      return get().selectedTags;
    }

    let nextTags: string[] = [];
    set((state) => {
      nextTags = state.selectedTags.includes(normalized)
        ? state.selectedTags.filter((value) => value !== normalized)
        : [...state.selectedTags, normalized];
      return { selectedTags: nextTags };
    });
    return nextTags;
  },

  clearTags: () => {
    set({ selectedTags: [] });
  },

  setSourceTier: (tier) => {
    set({ selectedSourceTier: tier });
  },

  clearError: () => {
    set({ error: null });
  },
}));
