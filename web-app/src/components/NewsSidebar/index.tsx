import { memo, useCallback, useEffect, useState } from 'react';
import type { NewsEvent, SourceTier } from '../../types/news';
import './NewsSidebar.css';

export type TimeRange = 'today' | 'yesterday' | '3days';

interface NewsSidebarProps {
  events: NewsEvent[];
  total?: number;
  selectedEventId?: string;
  selectedTags: string[];
  selectedSourceTier: SourceTier | null;
  onTagToggle: (tag: string) => void | Promise<void>;
  onTagClear: () => void | Promise<void>;
  onSourceTierChange: (tier: SourceTier | null) => void | Promise<void>;
  onEventClick: (eventId: string) => void;
}

const FAVORITES_KEY = 'ainewser.favorites';
const TOPIC_TAG_OPTIONS = [
  { value: 'ai', label: 'AI' },
  { value: 'chip', label: 'Chip' },
  { value: 'cybersecurity', label: 'Cyber' },
  { value: 'conflict', label: 'Conflict' },
  { value: 'disaster', label: 'Disaster' },
  { value: 'climate', label: 'Climate' },
  { value: 'science', label: 'Science' },
  { value: 'space', label: 'Space' },
  { value: 'policy', label: 'Policy' },
  { value: 'economy', label: 'Economy' },
] as const;
const SOURCE_TIER_OPTIONS: Array<{ value: SourceTier; label: string }> = [
  { value: 'official', label: 'Official' },
  { value: 'authoritative', label: 'Media' },
  { value: 'aggregator', label: 'Aggregate' },
  { value: 'community', label: 'Community' },
  { value: 'social', label: 'Social' },
];

function loadFavorites(): Set<string> {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as string[];
    return new Set(arr);
  } catch {
    return new Set();
  }
}

function saveFavorites(ids: Set<string>) {
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify([...ids]));
  } catch {
    // Ignore localStorage write errors in restricted contexts.
  }
}

function formatRelativeTime(isoString: string, now: number): string {
  const date = new Date(isoString);
  const diff = now - date.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString('en-US');
}

const NewsSidebar = memo(
  ({
    events,
    total: _total,
    selectedEventId,
    selectedTags,
    selectedSourceTier,
    onTagToggle,
    onTagClear,
    onSourceTierChange,
    onEventClick,
  }: NewsSidebarProps) => {
    const [activeTab, setActiveTab] = useState<'hot' | 'favorites' | 'video'>('hot');
    const [timeRange, setTimeRange] = useState<TimeRange>('today');
    const [favorites, setFavorites] = useState<Set<string>>(() => loadFavorites());
    const [isTopicExpanded, setIsTopicExpanded] = useState(true);
    const [isSourceExpanded, setIsSourceExpanded] = useState(false);

    useEffect(() => {
      const handler = (e: Event) => {
        const ce = e as CustomEvent<{ eventId: string; favorited: boolean }>;
        setFavorites((prev) => {
          const next = new Set(prev);
          if (ce.detail.favorited) next.add(ce.detail.eventId);
          else next.delete(ce.detail.eventId);
          saveFavorites(next);
          return next;
        });
      };
      window.addEventListener('favorite-toggle', handler);
      return () => window.removeEventListener('favorite-toggle', handler);
    }, []);

    const now = Date.now();

    const isToday = useCallback((isoString: string) => {
      const d = new Date(isoString);
      const today = new Date();
      return d.getFullYear() === today.getFullYear()
        && d.getMonth() === today.getMonth()
        && d.getDate() === today.getDate();
    }, []);

    const isYesterday = useCallback((isoString: string) => {
      const d = new Date(isoString);
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      return d.getFullYear() === yesterday.getFullYear()
        && d.getMonth() === yesterday.getMonth()
        && d.getDate() === yesterday.getDate();
    }, []);

    const isWithin3Days = useCallback((isoString: string) => {
      const oneDay = 24 * 60 * 60 * 1000;
      const diff = now - new Date(isoString).getTime();
      return diff >= oneDay && diff <= 3 * oneDay;
    }, [now]);

    const filteredEvents = events.filter((event) => {
      if (activeTab === 'favorites') return favorites.has(event.id);
      if (activeTab === 'hot') {
        switch (timeRange) {
          case 'today':
            return isToday(event.first_seen_at);
          case 'yesterday':
            return isYesterday(event.first_seen_at);
          case '3days':
            return isWithin3Days(event.first_seen_at);
        }
      }
      return true;
    });

    const tagCounts = events.reduce<Record<string, number>>((acc, event) => {
      for (const tag of event.tags ?? []) {
        acc[tag] = (acc[tag] ?? 0) + 1;
      }
      return acc;
    }, {});

    const visibleTagOptions = TOPIC_TAG_OPTIONS.filter(
      ({ value }) => selectedTags.includes(value) || (tagCounts[value] ?? 0) > 0
    );

    const favCount = favorites.size;
    const tierCounts = events.reduce<Record<string, number>>((acc, event) => {
      const tier = event.source_tier;
      if (!tier) return acc;
      acc[tier] = (acc[tier] ?? 0) + 1;
      return acc;
    }, {});
    const visibleSourceOptions = SOURCE_TIER_OPTIONS.filter(
      ({ value }) => selectedSourceTier === value || (tierCounts[value] ?? 0) > 0
    );

    return (
      <div className="news-sidebar">
        <div className="sidebar-tabs">
          <button
            type="button"
            className={`sidebar-tab ${activeTab === 'hot' ? 'active' : ''}`}
            onClick={() => setActiveTab('hot')}
          >
            Hot
          </button>
          <button
            type="button"
            className={`sidebar-tab ${activeTab === 'favorites' ? 'active' : ''}`}
            onClick={() => setActiveTab('favorites')}
          >
            Favorites
            {favCount > 0 && <span className="tab-badge">{favCount}</span>}
          </button>
          <button
            type="button"
            className={`sidebar-tab ${activeTab === 'video' ? 'active' : ''}`}
            onClick={() => setActiveTab('video')}
          >
            Video
          </button>
        </div>

        {activeTab === 'hot' && (
          <>
            <div className="time-filters">
              {(['today', 'yesterday', '3days'] as TimeRange[]).map((range) => (
                <button
                  key={range}
                  type="button"
                  className={`time-btn ${timeRange === range ? 'active' : ''}`}
                  onClick={() => setTimeRange(range)}
                >
                  {range === 'today' ? 'Today' : range === 'yesterday' ? 'Yesterday' : 'Past 3d'}
                </button>
              ))}
            </div>

            <div className="filter-section">
              <button
                type="button"
                className="filter-section-toggle"
                onClick={() => setIsTopicExpanded((prev) => !prev)}
                aria-expanded={isTopicExpanded}
              >
                <span className={`filter-section-arrow ${isTopicExpanded ? 'expanded' : ''}`} aria-hidden />
                <span className="filter-section-title">Topics</span>
                <span className="filter-section-meta">{visibleTagOptions.length + 1}</span>
              </button>
              <div className={`filter-section-body ${isTopicExpanded ? 'expanded' : ''}`}>
                <div className="filter-chip-grid">
                  <button
                    type="button"
                    className={`topic-chip topic-chip--all ${selectedTags.length === 0 ? 'active' : ''}`}
                    onClick={() => void onTagClear()}
                  >
                    <span>All</span>
                  </button>
                  {visibleTagOptions.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      className={`topic-chip ${selectedTags.includes(value) ? 'active' : ''}`}
                      onClick={() => void onTagToggle(value)}
                    >
                      <span>{label}</span>
                      <span className="topic-chip-count">{tagCounts[value] ?? 0}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="filter-section">
              <button
                type="button"
                className="filter-section-toggle"
                onClick={() => setIsSourceExpanded((prev) => !prev)}
                aria-expanded={isSourceExpanded}
              >
                <span className={`filter-section-arrow ${isSourceExpanded ? 'expanded' : ''}`} aria-hidden />
                <span className="filter-section-title">Sources</span>
                <span className="filter-section-meta">{visibleSourceOptions.length + 1}</span>
              </button>
              <div className={`filter-section-body ${isSourceExpanded ? 'expanded' : ''}`}>
                <div className="filter-chip-grid">
                  <button
                    type="button"
                    className={`source-chip ${selectedSourceTier === null ? 'active' : ''}`}
                    onClick={() => void onSourceTierChange(null)}
                  >
                    <span>All Sources</span>
                  </button>
                  {visibleSourceOptions.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      className={`source-chip ${selectedSourceTier === value ? 'active' : ''}`}
                      onClick={() => void onSourceTierChange(value)}
                    >
                      <span>{label}</span>
                      <span className="source-chip-count">{tierCounts[value] ?? 0}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        <div className="sidebar-header">
          {activeTab === 'hot' && (
            <h2 className="sidebar-title">
              {timeRange === 'today' ? 'Today' : timeRange === 'yesterday' ? 'Yesterday' : 'Past 3 days'}
            </h2>
          )}
          {activeTab === 'favorites' && <h2 className="sidebar-title">Favorites</h2>}
          {activeTab === 'video' && <h2 className="sidebar-title">Video Feed</h2>}
          {activeTab !== 'video' && (
            <span className="sidebar-count">{filteredEvents.length} events</span>
          )}
        </div>

        <div className="sidebar-list">
          {activeTab === 'video' ? (
            <div className="sidebar-video-placeholder">
              <div className="video-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              </div>
              <p className="video-title">Video feed is coming soon</p>
              <p className="video-subtitle">This area is reserved for future short-form updates.</p>
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="sidebar-empty">
              <p>{activeTab === 'favorites' ? 'No favorites yet' : 'No events in this view'}</p>
            </div>
          ) : (
            filteredEvents.map((event) => (
              <div
                key={event.id}
                className={`sidebar-item ${selectedEventId === event.id ? 'selected' : ''}`}
                onClick={() => onEventClick(event.id)}
              >
                <div className="item-header">
                  <span className="item-country">{event.main_country || 'Unknown'}</span>
                  <span className="item-time">{formatRelativeTime(event.first_seen_at, now)}</span>
                </div>
                <h3 className="item-title">{event.title}</h3>
                {!!event.tags?.length && (
                  <div className="item-tags">
                    {event.tags.slice(0, 3).map((tag) => (
                      <span key={`${event.id}-${tag}`} className="item-tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <div className="item-footer">
                  {event.source_tier && (
                    <span className={`item-tier item-tier--${event.source_tier}`}>
                      {event.source_tier}
                    </span>
                  )}
                  <span className="item-heat">Heat {event.heat_score}</span>
                  <span className="item-articles">{event.article_count} articles</span>
                  {favorites.has(event.id) && (
                    <span className="item-star favorited" title="Favorited">Star</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    );
  }
);

NewsSidebar.displayName = 'NewsSidebar';

export default NewsSidebar;
