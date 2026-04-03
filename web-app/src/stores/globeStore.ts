// Globe store using Zustand
import { create } from 'zustand';
import { globeApi } from '../services/api';
import { DEFAULT_RECENT_HOURS } from '../utils/timeUtils';
import type { Hotspot, HotspotListResponse } from '../types/news';

interface GlobeState {
  // State
  hotspots: Hotspot[];
  hoveredHotspot: Hotspot | null;
  isLoading: boolean;
  error: string | null;
  currentScope: 'all' | 'china' | 'world';

  // Globe controls
  globeRotation: boolean;
  autoRotateSpeed: number;

  // Actions
  fetchHotspots: (params?: { scope?: string; min_heat?: number; limit?: number }) => Promise<void>;
  setHoveredHotspot: (hotspot: Hotspot | null) => void;
  setScope: (scope: 'all' | 'china' | 'world') => void;
  toggleRotation: () => void;
  setGlobeRotation: (enabled: boolean) => void;
  clearError: () => void;
}

export const useGlobeStore = create<GlobeState>((set, get) => ({
  // Initial state
  hotspots: [],
  hoveredHotspot: null,
  isLoading: false,
  error: null,
  currentScope: 'all',
  globeRotation: true,
  autoRotateSpeed: 0.5,

  // Actions
  fetchHotspots: async (params = {}) => {
    set({ isLoading: true, error: null });

    try {
      const nextScope = (params.scope as 'all' | 'china' | 'world' | undefined) ?? get().currentScope;
      if (params.scope) {
        set({ currentScope: nextScope });
      }

      const response = await globeApi.getHotspots({
        scope: nextScope,
        since_hours: DEFAULT_RECENT_HOURS,
        ...params,
      });

      const data = response as unknown as HotspotListResponse;

      set({
        hotspots: data.hotspots,
        isLoading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch hotspots',
        isLoading: false,
      });
    }
  },

  setHoveredHotspot: (hotspot) => {
    set({ hoveredHotspot: hotspot });
  },

  setScope: (scope) => {
    set({ currentScope: scope });
    get().fetchHotspots({ scope });
  },

  toggleRotation: () => {
    set((state) => ({ globeRotation: !state.globeRotation }));
  },

  setGlobeRotation: (enabled: boolean) => {
    set({ globeRotation: enabled });
  },

  clearError: () => {
    set({ error: null });
  },
}));
