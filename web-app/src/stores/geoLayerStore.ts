import { create } from 'zustand';
import { hotspotsApi } from '../services/api';
import { hoursSinceBeijingMidnight } from '../utils/timeUtils';
import type {
  CountryHotspotItem,
  CountryHotspotListResponse,
  Admin1HotspotItem,
  Admin1HotspotListResponse,
  CityHotspotItem,
  CityHotspotListResponse,
} from '../types/news';

export type GeoLayer = 'global' | 'country';

type GeoFeature = { type: string; geometry: object; properties?: Record<string, unknown> };

interface GeoLayerState {
  layer: GeoLayer;
  countryHotspots: CountryHotspotItem[];
  countryHeatMap: Map<string, number>;
  countryEventCountMap: Map<string, number>;
  selectedCountryCode: string | null;
  selectedCountryName: string | null;
  admin1Hotspots: Admin1HotspotItem[];
  admin1HeatMap: Map<string, number>;
  admin1EventCountMap: Map<string, number>;
  cityHotspots: CityHotspotItem[];
  admin1GeoJsonUrl: string | null;
  admin1GeoJsonReady: boolean;
  admin1Features: GeoFeature[];
  isLoadingCountries: boolean;
  isLoadingAdmin1: boolean;
  error: string | null;
  fetchCountryHotspots: (scope?: string) => Promise<void>;
  selectCountry: (countryCode: string, countryName: string, iso3: string) => Promise<void>;
  refreshActiveLayer: () => Promise<void>;
  backToGlobal: () => void;
  clearError: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL || '/api';

function buildAdmin1GeoJsonUrl(countryCode: string): string {
  const base = API_BASE.replace(/\/api$/, '');
  return `${base}/static/geodata/admin1/${countryCode.toUpperCase()}.geojson`;
}

const admin1GeoCache = new Map<string, GeoFeature[]>();

async function fetchAdmin1LayerData(countryCode: string) {
  const cc = countryCode.toUpperCase();
  const geoUrl = buildAdmin1GeoJsonUrl(cc);

  const cachedFeatures = admin1GeoCache.get(cc);
  const geoPromise: Promise<GeoFeature[]> = cachedFeatures
    ? Promise.resolve(cachedFeatures)
    : fetch(geoUrl)
        .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
        .then((data: { features?: GeoFeature[] }) => {
          const features = data.features ?? [];
          admin1GeoCache.set(cc, features);
          return features;
        });

  const sinceHours = hoursSinceBeijingMidnight();
  const [hotspotsResult, geoResult, cityResult] = await Promise.allSettled([
    hotspotsApi.getAdmin1Hotspots(cc, { since_hours: sinceHours }),
    geoPromise,
    hotspotsApi.getCityHotspots(cc, { limit: 30, since_hours: sinceHours }),
  ]);

  const admin1List =
    hotspotsResult.status === 'fulfilled'
      ? (hotspotsResult.value as unknown as Admin1HotspotListResponse).admin1_list
      : [];

  const cityList =
    cityResult.status === 'fulfilled'
      ? (cityResult.value as unknown as CityHotspotListResponse).cities
      : [];

  const admin1HeatMap = new Map<string, number>();
  const admin1EventCountMap = new Map<string, number>();

  for (const item of admin1List) {
    if (item.admin1_code) {
      admin1HeatMap.set(item.admin1_code, item.heat_total);
      admin1EventCountMap.set(item.admin1_code, item.event_count);
    }
    if (item.admin1_name) {
      const key = item.admin1_name.toLowerCase();
      admin1HeatMap.set(key, item.heat_total);
      admin1EventCountMap.set(key, item.event_count);
    }
  }

  return {
    admin1Hotspots: admin1List,
    admin1HeatMap,
    admin1EventCountMap,
    cityHotspots: cityList,
    admin1GeoJsonReady: geoResult.status === 'fulfilled',
    admin1Features: geoResult.status === 'fulfilled' ? geoResult.value : [],
    error: hotspotsResult.status === 'rejected' ? 'Failed to fetch admin1 data' : null,
  };
}

export const useGeoLayerStore = create<GeoLayerState>((set) => ({
  layer: 'global',
  countryHotspots: [],
  countryHeatMap: new Map(),
  countryEventCountMap: new Map(),
  selectedCountryCode: null,
  selectedCountryName: null,
  admin1Hotspots: [],
  admin1HeatMap: new Map(),
  admin1EventCountMap: new Map(),
  cityHotspots: [],
  admin1GeoJsonUrl: null,
  admin1GeoJsonReady: false,
  admin1Features: [],
  isLoadingCountries: false,
  isLoadingAdmin1: false,
  error: null,

  fetchCountryHotspots: async (scope) => {
    set({ isLoadingCountries: true, error: null });
    try {
      const response = await hotspotsApi.getCountryHotspots({
        scope,
        limit: 100,
        since_hours: hoursSinceBeijingMidnight(),
      });
      const data = response as unknown as CountryHotspotListResponse;
      const countryHeatMap = new Map<string, number>();
      const countryEventCountMap = new Map<string, number>();

      for (const country of data.countries) {
        if (!country.iso_a3) continue;
        const iso3 = country.iso_a3.toUpperCase();
        countryHeatMap.set(iso3, country.heat_total);
        countryEventCountMap.set(iso3, country.event_count);
      }

      set({
        countryHotspots: data.countries,
        countryHeatMap,
        countryEventCountMap,
        isLoadingCountries: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch country hotspots',
        isLoadingCountries: false,
      });
    }
  },

  selectCountry: async (countryCode, countryName) => {
    const cc = countryCode.toUpperCase();
    set({
      layer: 'country',
      selectedCountryCode: cc,
      selectedCountryName: countryName,
      admin1Hotspots: [],
      cityHotspots: [],
      admin1GeoJsonUrl: buildAdmin1GeoJsonUrl(cc),
      admin1GeoJsonReady: false,
      isLoadingAdmin1: true,
      error: null,
    });

    const nextState = await fetchAdmin1LayerData(cc);
    set({
      ...nextState,
      isLoadingAdmin1: false,
    });
  },

  refreshActiveLayer: async () => {
    const state = useGeoLayerStore.getState();
    await state.fetchCountryHotspots();
    if (state.layer === 'country' && state.selectedCountryCode) {
      set({ isLoadingAdmin1: true, error: null });
      try {
        const nextState = await fetchAdmin1LayerData(state.selectedCountryCode);
        set({
          ...nextState,
          isLoadingAdmin1: false,
        });
      } catch (error) {
        set({
          error: error instanceof Error ? error.message : 'Failed to refresh regional data',
          isLoadingAdmin1: false,
        });
      }
      return;
    }
  },

  backToGlobal: () => {
    set({
      layer: 'global',
      selectedCountryCode: null,
      selectedCountryName: null,
      admin1Hotspots: [],
      admin1HeatMap: new Map(),
      admin1EventCountMap: new Map(),
      cityHotspots: [],
      admin1GeoJsonUrl: null,
      admin1GeoJsonReady: false,
      admin1Features: [],
    });
  },

  clearError: () => set({ error: null }),
}));
