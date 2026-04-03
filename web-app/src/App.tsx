import { useState, useEffect, useCallback, useRef } from 'react';
import GlobeScene from './components/GlobeScene';
import NewsSidebar from './components/NewsSidebar';
import NewsDetailPanel from './components/NewsDetailPanel';
import { useNewsStore } from './stores/newsStore';
import { useGlobeStore } from './stores/globeStore';
import { jobsApi, newsApi } from './services/api';
import { DEFAULT_RECENT_HOURS } from './utils/timeUtils';
import type { Hotspot } from './types/news';
import './App.css';

const POLL_MS = 45_000;

function App() {
  const { selectedEvent, setSelectedEvent, events, total, fetchHotEvents, isLoading } = useNewsStore();
  const { hotspots, fetchHotspots } = useGlobeStore();
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [manualRefresh, setManualRefresh] = useState(false);
  type RegionEntry = { name: string; hotspots: Hotspot[]; geoKey?: string };
  const [regionStack, setRegionStack] = useState<RegionEntry[]>([]);
  const regionPanel = regionStack.length > 0 ? regionStack[regionStack.length - 1] : null;
  // Only admin1+ entries in breadcrumb — country is shown separately via selectedCountryName
  const regionBreadcrumb = regionStack.length > 1 ? regionStack.slice(1).map((r) => r.name) : [];
  const crawlPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshData = useCallback(async () => {
    await fetchHotEvents({ scope: 'all', page: 1 });
    await fetchHotspots({ scope: 'all' });
  }, [fetchHotEvents, fetchHotspots]);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshData();
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [refreshData]);

  const handleManualCrawl = async () => {
    if (crawlPollRef.current != null) {
      window.clearInterval(crawlPollRef.current);
      crawlPollRef.current = null;
    }
    setManualRefresh(true);
    try {
      await jobsApi.triggerCrawl({
        maxItems: 80,
        crawlScope: 'all',
      });
      await refreshData();
    } catch {
      await refreshData();
    } finally {
      setManualRefresh(false);
    }
    const pollMs = 5000;
    const maxMs = 180000;
    crawlPollRef.current = window.setInterval(() => {
      void refreshData();
    }, pollMs);
    window.setTimeout(() => {
      if (crawlPollRef.current != null) {
        window.clearInterval(crawlPollRef.current);
        crawlPollRef.current = null;
      }
    }, maxMs);
  };

  const handleHotspotClick = (eventId: string) => {
    const event = events.find((e) => e.id === eventId);
    if (event) {
      setRegionStack([]);
      setSelectedEvent(event);
      setIsDetailOpen(true);
    }
  };

  const handleAdmin1RegionClick = useCallback((
    _regionHotspots: Hotspot[],
    regionName: string,
    countryName: string,
    geoKey?: string,
  ) => {
    setSelectedEvent(null);
    setIsDetailOpen(false);
    const label = countryName ? `${regionName} · ${countryName}` : regionName;
    const isAdminDrillDown = countryName !== '';

    if (isAdminDrillDown) {
      // Admin1 drill-down: if already at admin1 depth, REPLACE the current entry (same-level switch).
      // Only push when drilling deeper (first time into admin1 from country level).
      setRegionStack((prev) =>
        prev.length >= 2
          ? [...prev.slice(0, -1), { name: label, hotspots: [], geoKey }]
          : [...prev, { name: label, hotspots: [], geoKey }]
      );
      // Keep region detail aligned with the globe/news time window.
      if (geoKey) {
        newsApi.getRegionNews(geoKey, { page_size: 40, since_hours: DEFAULT_RECENT_HOURS })
          .then((resp: any) => {
            const rawItems = Array.isArray(resp) ? resp : (resp?.items ?? []);
            const items: Hotspot[] = rawItems.map((e: any) => ({
              event_id: e.id,
              title: e.title,
              summary: e.summary,
              heat_score: e.heat_score,
              geo_key: geoKey,
              geo_type: 'admin1' as const,
              display_type: 'polygon' as const,
              center: null,
              iso_a3: e.iso_a3 ?? null,
              article_count: e.article_count ?? 1,
              confidence: 1,
            }));
            setRegionStack((prev) =>
              prev.map((entry) =>
                entry.geoKey === geoKey ? { ...entry, hotspots: items } : entry
              )
            );
          })
          .catch(() => { /* panel stays empty */ });
      }
    } else {
      // Country click: keep the region panel aligned with the same recent window.
      setRegionStack([{ name: label, hotspots: [], geoKey }]);
      if (geoKey) {
        newsApi.getRegionNews(geoKey, { page_size: 40, since_hours: DEFAULT_RECENT_HOURS })
          .then((resp: any) => {
            const rawItems = Array.isArray(resp) ? resp : (resp?.items ?? []);
            const items: Hotspot[] = rawItems.map((e: any) => ({
              event_id: e.id,
              title: e.title,
              summary: e.summary,
              heat_score: e.heat_score,
              geo_key: geoKey,
              geo_type: 'country' as const,
              display_type: 'polygon' as const,
              center: null,
              iso_a3: e.iso_a3 ?? null,
              article_count: e.article_count ?? 1,
              confidence: 1,
            }));
            setRegionStack((prev) =>
              prev.map((entry) =>
                entry.geoKey === geoKey ? { ...entry, hotspots: items } : entry
              )
            );
          })
          .catch(() => { /* panel stays empty */ });
      }
    }
  }, []);

  /** Pop regionStack back to the country-level entry (index 0) */
  const handleCountryBreadcrumbClick = useCallback(() => {
    setRegionStack((prev) => (prev.length > 1 ? [prev[0]] : prev));
  }, []);

  const handleRegionHotspotClick = (eventId: string) => {
    setRegionStack([]);
    handleHotspotClick(eventId);
  };

  const handleCloseRegionPanel = () => {
    setRegionStack([]);
  };

  const handleRegionBack = () => {
    setRegionStack((prev) => prev.slice(0, -1));
  };

  const handleEventClick = (eventId: string) => {
    const event = events.find((e) => e.id === eventId);
    if (event) {
      setSelectedEvent(event);
      setIsDetailOpen(true);
    }
  };

  const handleCloseDetail = () => {
    setIsDetailOpen(false);
  };

  return (
    <div className="app">
      <header className="app-header app-header--minimal">
        <h1 className="app-title">AiNewser</h1>
        <div className="header-actions">
          <button
            type="button"
            className="header-refresh"
            title="更新新闻（后台爬虫）"
            disabled={manualRefresh || isLoading}
            onClick={handleManualCrawl}
          >
            <span className={`header-refresh-icon ${manualRefresh || isLoading ? 'spinning' : ''}`} aria-hidden>
              ↻
            </span>
            <span className="header-refresh-label">更新</span>
          </button>
        </div>
      </header>

      <main className="app-main">
        <aside className="app-sidebar">
          <NewsSidebar
            events={events}
            total={total}
            selectedEventId={selectedEvent?.id}
            onEventClick={handleEventClick}
          />
        </aside>

        <section className="app-globe">
          <GlobeScene
            hotspots={hotspots}
            onHotspotClick={handleHotspotClick}
            onAdmin1RegionClick={handleAdmin1RegionClick}
            regionBreadcrumb={regionBreadcrumb}
            onRegionBreadcrumbBack={regionStack.length > 1 ? handleRegionBack : undefined}
            onCountryBreadcrumbClick={regionStack.length > 1 ? handleCountryBreadcrumbClick : undefined}
          />
        </section>

        <aside className={`app-detail ${isDetailOpen || regionPanel ? 'open' : ''}`}>
          <NewsDetailPanel
            event={selectedEvent}
            isOpen={isDetailOpen || !!regionPanel}
            onClose={regionPanel ? handleCloseRegionPanel : handleCloseDetail}
            onBack={regionStack.length > 1 ? handleRegionBack : undefined}
            regionHotspots={regionPanel?.hotspots ?? null}
            regionName={regionPanel?.name ?? null}
            onRegionHotspotClick={handleRegionHotspotClick}
          />
        </aside>
      </main>
    </div>
  );
}

export default App;
