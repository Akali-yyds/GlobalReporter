// Geo layer store — manages global / country / admin1 drill-down state
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
  // Current display layer
  layer: GeoLayer;

  // Country-level aggregated hotspots (for polygon tinting)
  countryHotspots: CountryHotspotItem[];
  countryHeatMap: Map<string, number>; // iso_a3 -> heat_total
  countryEventCountMap: Map<string, number>; // iso_a3 -> event_count

  // Admin1 drill-down state
  selectedCountryCode: string | null;   // ISO-3166-1 alpha-2
  selectedCountryName: string | null;
  admin1Hotspots: Admin1HotspotItem[];
  admin1HeatMap: Map<string, number>;   // admin1_code -> heat_total
  admin1EventCountMap: Map<string, number>; // admin1_code -> event_count
  cityHotspots: CityHotspotItem[];       // city-level hotspots within selected country

  // Admin1 GeoJSON features (loaded on demand)
  admin1GeoJsonUrl: string | null;
  admin1GeoJsonReady: boolean;
  admin1Features: GeoFeature[];

  // Loading states
  isLoadingCountries: boolean;
  isLoadingAdmin1: boolean;
  error: string | null;

  // Actions
  fetchCountryHotspots: (scope?: string) => Promise<void>;
  selectCountry: (countryCode: string, countryName: string, iso3: string) => Promise<void>;
  backToGlobal: () => void;
  clearError: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL || '/api';

/** Build local static GeoJSON URL for admin1 boundaries */
function buildAdmin1GeoJsonUrl(countryCode: string): string {
  const base = API_BASE.replace(/\/api$/, '');
  return `${base}/static/geodata/admin1/${countryCode.toUpperCase()}.geojson`;
}

/** Module-level cache: countryCode (uppercase) → admin1 GeoJSON features */
const _admin1GeoCache = new Map<string, GeoFeature[]>();

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
      const resp = await hotspotsApi.getCountryHotspots({ scope, limit: 100, since_hours: hoursSinceBeijingMidnight() });
      const data = resp as unknown as CountryHotspotListResponse;
      const heatMap = new Map<string, number>();
      const eventCountMap = new Map<string, number>();
      for (const c of data.countries) {
        if (c.iso_a3) {
          const iso3 = c.iso_a3.toUpperCase();
          heatMap.set(iso3, c.heat_total);
          eventCountMap.set(iso3, c.event_count);
        }
      }
      set({
        countryHotspots: data.countries,
        countryHeatMap: heatMap,
        countryEventCountMap: eventCountMap,
        isLoadingCountries: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch country hotspots',
        isLoadingCountries: false,
      });
    }
  },

  selectCountry: async (countryCode, countryName, _iso3) => {
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

    const geoUrl = buildAdmin1GeoJsonUrl(cc);

    // Use cached GeoJSON if available; otherwise fetch and cache
    const cachedFeatures = _admin1GeoCache.get(cc);
    const geoPromise: Promise<GeoFeature[]> = cachedFeatures
      ? Promise.resolve(cachedFeatures)
      : fetch(geoUrl)
          .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
          .then((data: { features?: GeoFeature[] }) => {
            const features = data.features ?? [];
            _admin1GeoCache.set(cc, features);
            return features;
          });

    // Fetch admin1 hotspots, city hotspots, and GeoJSON in parallel
    const sh = hoursSinceBeijingMidnight();
    const [hotspotsResult, geoResult, cityResult] = await Promise.allSettled([
      hotspotsApi.getAdmin1Hotspots(cc, { since_hours: sh }),
      geoPromise,
      hotspotsApi.getCityHotspots(cc, { limit: 30, since_hours: sh }),
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
    for (const a of admin1List) {
      if (a.admin1_code) {
        admin1HeatMap.set(a.admin1_code, a.heat_total);
        admin1EventCountMap.set(a.admin1_code, a.event_count);
      }
      // Also index by English name (lowercase) so Natural Earth iso_3166_2 mismatches
      // (e.g. CN: GeoNames "22" vs NE "BJ") can fall back to name-based lookup
      if (a.admin1_name) {
        const key = a.admin1_name.toLowerCase();
        admin1HeatMap.set(key, a.heat_total);
        admin1EventCountMap.set(key, a.event_count);
      }
    }

    const admin1Features: GeoFeature[] =
      geoResult.status === 'fulfilled' ? geoResult.value : [];

    set({
      admin1Hotspots: admin1List,
      admin1HeatMap,
      admin1EventCountMap,
      cityHotspots: cityList,
      admin1GeoJsonReady: geoResult.status === 'fulfilled',
      admin1Features,
      isLoadingAdmin1: false,
      error: hotspotsResult.status === 'rejected' ? 'Failed to fetch admin1 data' : null,
    });
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
