// API service layer
import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if needed
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('token');
    }
    return Promise.reject(error);
  }
);

export default apiClient;

// News API
export const newsApi = {
  getHotNews: (params?: { page?: number; page_size?: number; scope?: string; category?: string; since_hours?: number }) =>
    apiClient.get('/news/hot', { params }),

  getNewsDetail: (eventId: string) =>
    apiClient.get(`/news/events/${eventId}`),

  getRegionNews: (geoKey: string, params?: { page?: number; page_size?: number; since_hours?: number }) =>
    apiClient.get(`/globe/regions/${geoKey}/news`, { params }),
};

// Globe API
export const globeApi = {
  getHotspots: (params?: { scope?: string; min_heat?: number; limit?: number; since_hours?: number }) =>
    apiClient.get('/globe/hotspots', { params }),
};

// Hotspots API (country/admin1 aggregation)
export const hotspotsApi = {
  getCountryHotspots: (params?: { scope?: string; min_heat?: number; limit?: number; since_hours?: number }) =>
    apiClient.get('/hotspots/countries', { params }),

  getAdmin1Hotspots: (countryCode: string, params?: { limit?: number; since_hours?: number }) =>
    apiClient.get(`/hotspots/admin1/${countryCode.toUpperCase()}`, { params }),

  getCityHotspots: (countryCode: string, params?: { limit?: number; min_heat?: number; since_hours?: number }) =>
    apiClient.get(`/hotspots/cities/${countryCode.toUpperCase()}`, { params }),
};

// Sources API
export const sourcesApi = {
  getSources: () => apiClient.get('/sources'),
};

// Jobs API
export const jobsApi = {
  getLatestJob: () => apiClient.get('/jobs/latest'),
  /**
   * Manual crawl (background). Uses JSON body:
   * - max_items: total budget (split across spiders when crawl_scope is set)
   * - crawl_scope: china | world | all — multiple sources; omit for single spider
   */
  triggerCrawl: (options?: {
    maxItems?: number;
    crawlScope?: 'china' | 'world' | 'all';
    spider?: string;
  }) =>
    apiClient.post('/jobs/crawl', {
      max_items: options?.maxItems ?? 50,
      crawl_scope: options?.crawlScope ?? undefined,
      spider: options?.spider ?? undefined,
    }),
};
