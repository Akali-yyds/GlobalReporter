import { useState, useEffect, useCallback, useRef } from 'react';
import GlobeScene from './components/GlobeScene';
import NewsSidebar from './components/NewsSidebar';
import NewsDetailPanel from './components/NewsDetailPanel';
import { useNewsStore } from './stores/newsStore';
import { useGlobeStore } from './stores/globeStore';
import { jobsApi, newsApi } from './services/api';
import { hoursSinceBeijingMidnight, type NewsTimeRange } from './utils/timeUtils';
import type { Hotspot, SourceTier } from './types/news';
import type { VideoRolloutState, VideoType } from './types/video';
import './App.css';

const POLL_MS = 45_000;

function dedupeHotspotsByEventId(hotspots: Hotspot[]): Hotspot[] {
  const unique = new Map<string, Hotspot>();

  hotspots.forEach((hotspot, index) => {
    const eventId = hotspot.event_id || `${hotspot.geo_key || 'geo'}-${index}`;
    const existing = unique.get(eventId);
    if (!existing || hotspot.heat_score > existing.heat_score) {
      unique.set(eventId, hotspot);
    }
  });

  return Array.from(unique.values());
}

function mapRegionHotspots(
  hotspots: Hotspot[],
  geoKey: string | undefined,
  geoType: 'country' | 'region'
): Hotspot[] {
  if (!geoKey) return [];
  return dedupeHotspotsByEventId(hotspots).map((hotspot) => ({
    ...hotspot,
    geo_key: hotspot.geo_key || geoKey,
    geo_type: geoType,
    display_type: hotspot.display_type || 'polygon',
    center: hotspot.center ?? undefined,
    confidence: hotspot.confidence ?? 1,
  }));
}

function App() {
  const {
    selectedEvent,
    setSelectedEvent,
    events,
    total,
    fetchHotEvents,
    isLoading,
    selectedTags,
    selectedSourceTier,
    toggleTag,
    clearTags,
    setSourceTier,
  } = useNewsStore();
  const { hotspots, fetchHotspots } = useGlobeStore();
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [manualRefresh, setManualRefresh] = useState(false);
  const [timeRange, setTimeRange] = useState<NewsTimeRange>('today');
  const [activeTab, setActiveTab] = useState<'hot' | 'favorites' | 'video'>('hot');
  const [videoProvider, setVideoProvider] = useState<'all' | 'youtube' | 'direct_hls'>('all');
  const [videoType, setVideoType] = useState<'all' | VideoType>('all');
  const [videoRolloutState, setVideoRolloutState] = useState<'all' | VideoRolloutState>('all');
  const [videoTopic, setVideoTopic] = useState<string | null>(null);
  type RegionEntry = { name: string; hotspots: Hotspot[]; geoKey?: string };
  const [regionStack, setRegionStack] = useState<RegionEntry[]>([]);
  const regionPanel = regionStack.length > 0 ? regionStack[regionStack.length - 1] : null;
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
    regionHotspots: Hotspot[],
    regionName: string,
    countryName: string,
    geoKey?: string,
  ) => {
    setSelectedEvent(null);
    setIsDetailOpen(false);
    const label = countryName ? `${regionName} · ${countryName}` : regionName;
    const isAdminDrillDown = countryName !== '';
    const seededHotspots = mapRegionHotspots(
      regionHotspots,
      geoKey,
      isAdminDrillDown ? 'region' : 'country'
    );

    if (isAdminDrillDown) {
      setRegionStack((prev) =>
        prev.length >= 2
          ? [...prev.slice(0, -1), { name: label, hotspots: seededHotspots, geoKey }]
          : [...prev, { name: label, hotspots: seededHotspots, geoKey }]
      );
      if (geoKey) {
        newsApi.getRegionNews(geoKey, { page_size: 40, since_hours: hoursSinceBeijingMidnight() })
          .then((resp: any) => {
            const rawItems = Array.isArray(resp) ? resp : (resp?.items ?? []);
            const items = dedupeHotspotsByEventId(rawItems.map((e: any) => ({
              event_id: e.id,
              title: e.title,
              summary: e.summary,
              heat_score: e.heat_score,
              geo_key: geoKey,
              geo_type: 'region' as const,
              display_type: 'polygon' as const,
              center: undefined,
              iso_a3: e.iso_a3 ?? null,
              article_count: e.article_count ?? 1,
              confidence: 1,
            })));
            if (items.length > 0) {
              setRegionStack((prev) =>
                prev.map((entry) =>
                  entry.geoKey === geoKey ? { ...entry, hotspots: items } : entry
                )
              );
            }
          })
          .catch(() => {});
      }
      return;
    }

    setRegionStack([{ name: label, hotspots: seededHotspots, geoKey }]);
    if (geoKey) {
      newsApi.getRegionNews(geoKey, { page_size: 40, since_hours: hoursSinceBeijingMidnight() })
        .then((resp: any) => {
          const rawItems = Array.isArray(resp) ? resp : (resp?.items ?? []);
          const items = dedupeHotspotsByEventId(rawItems.map((e: any) => ({
            event_id: e.id,
            title: e.title,
            summary: e.summary,
            heat_score: e.heat_score,
            geo_key: geoKey,
            geo_type: 'country' as const,
            display_type: 'polygon' as const,
            center: undefined,
            iso_a3: e.iso_a3 ?? null,
            article_count: e.article_count ?? 1,
            confidence: 1,
          })));
          if (items.length > 0) {
            setRegionStack((prev) =>
              prev.map((entry) =>
                entry.geoKey === geoKey ? { ...entry, hotspots: items } : entry
              )
            );
          }
        })
        .catch(() => {});
    }
  }, [setSelectedEvent]);

  const handleCountryBreadcrumbClick = useCallback(() => {
    setRegionStack((prev) => (prev.length > 1 ? [prev[0]] : prev));
  }, []);

  const handleBackToGlobal = useCallback(() => {
    setRegionStack([]);
    setSelectedEvent(null);
    setIsDetailOpen(false);
  }, [setSelectedEvent]);

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

  const handleTagToggle = useCallback((tag: string) => {
    toggleTag(tag);
  }, [toggleTag]);

  const handleTagClear = useCallback(() => {
    clearTags();
  }, [clearTags]);

  const handleSourceTierChange = useCallback((tier: SourceTier | null) => {
    setSourceTier(tier);
  }, [setSourceTier]);

  const handleSidebarTabChange = useCallback((tab: 'hot' | 'favorites' | 'video') => {
    setActiveTab(tab);
    if (tab === 'video') {
      setRegionStack([]);
      setSelectedEvent(null);
      setIsDetailOpen(false);
    }
  }, [setSelectedEvent]);

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
            title="Update news"
            disabled={manualRefresh || isLoading}
            onClick={handleManualCrawl}
            style={{ display: activeTab === 'video' ? 'none' : 'inline-flex' }}
          >
            <span className={`header-refresh-icon ${manualRefresh || isLoading ? 'spinning' : ''}`} aria-hidden>
              ↻
            </span>
            <span className="header-refresh-label">Update</span>
          </button>
        </div>
      </header>

      <main className="app-main">
        <aside className="app-sidebar">
          <NewsSidebar
            events={events}
            total={total}
            selectedEventId={selectedEvent?.id}
            activeTab={activeTab}
            timeRange={timeRange}
            selectedTags={selectedTags}
            selectedSourceTier={selectedSourceTier}
            videoProvider={videoProvider}
            videoType={videoType}
            videoRolloutState={videoRolloutState}
            videoTopic={videoTopic}
            onTimeRangeChange={setTimeRange}
            onTabChange={handleSidebarTabChange}
            onTagToggle={handleTagToggle}
            onTagClear={handleTagClear}
            onSourceTierChange={handleSourceTierChange}
            onVideoProviderChange={setVideoProvider}
            onVideoTypeChange={setVideoType}
            onVideoRolloutStateChange={setVideoRolloutState}
            onVideoTopicChange={setVideoTopic}
            onEventClick={handleEventClick}
          />
        </aside>

        <section className="app-globe">
          <GlobeScene
            hotspots={hotspots}
            onHotspotClick={handleHotspotClick}
            onAdmin1RegionClick={handleAdmin1RegionClick}
            onBackToGlobal={handleBackToGlobal}
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
