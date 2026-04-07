import { memo, useEffect, useState } from 'react';
import type { NewsEvent, SourceTier } from '../../types/news';
import type { VideoRolloutState, VideoType } from '../../types/video';
import LiveVideos from '../../pages/LiveVideos';
import { isEventInTimeRange, parseApiDate, type NewsTimeRange } from '../../utils/timeUtils';
import './NewsSidebar.css';

interface NewsSidebarProps {
  events: NewsEvent[];
  total?: number;
  selectedEventId?: string;
  activeTab: 'hot' | 'favorites' | 'video';
  timeRange: NewsTimeRange;
  selectedTags: string[];
  selectedSourceTier: SourceTier | null;
  videoProvider: 'all' | 'youtube' | 'direct_hls';
  videoType: 'all' | VideoType;
  videoRolloutState: 'all' | VideoRolloutState;
  videoTopic: string | null;
  onTimeRangeChange: (timeRange: NewsTimeRange) => void;
  onTabChange: (tab: 'hot' | 'favorites' | 'video') => void;
  onTagToggle: (tag: string) => void | Promise<void>;
  onTagClear: () => void | Promise<void>;
  onSourceTierChange: (tier: SourceTier | null) => void | Promise<void>;
  onVideoProviderChange: (provider: 'all' | 'youtube' | 'direct_hls') => void;
  onVideoTypeChange: (videoType: 'all' | VideoType) => void;
  onVideoRolloutStateChange: (rolloutState: 'all' | VideoRolloutState) => void;
  onVideoTopicChange: (topic: string | null) => void;
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
const VIDEO_PROVIDER_OPTIONS = [
  { value: 'all', label: 'All Providers' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'direct_hls', label: 'Direct HLS' },
] as const;
const VIDEO_TYPE_OPTIONS = [
  { value: 'all', label: 'All Types' },
  { value: 'youtube_embed', label: 'YouTube Embed' },
  { value: 'hls', label: 'HLS' },
] as const;
const VIDEO_ROLLOUT_OPTIONS = [
  { value: 'all', label: 'All Rollouts' },
  { value: 'default', label: 'Default' },
  { value: 'canary', label: 'Canary' },
  { value: 'poc', label: 'PoC' },
  { value: 'paused', label: 'Paused' },
] as const;
const VIDEO_TOPIC_OPTIONS = [
  { value: null, label: 'All Topics' },
  { value: 'news', label: 'News' },
  { value: 'finance', label: 'Finance' },
  { value: 'breaking', label: 'Breaking' },
  { value: 'space', label: 'Space' },
  { value: 'official', label: 'Official' },
  { value: 'live', label: 'Live' },
  { value: 'hls', label: 'HLS' },
] as const;

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
  const date = parseApiDate(isoString);
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
    activeTab,
    timeRange,
    selectedTags,
    selectedSourceTier,
    videoProvider,
    videoType,
    videoRolloutState,
    videoTopic,
    onTimeRangeChange,
    onTabChange,
    onTagToggle,
    onTagClear,
    onSourceTierChange,
    onVideoProviderChange,
    onVideoTypeChange,
    onVideoRolloutStateChange,
    onVideoTopicChange,
    onEventClick,
  }: NewsSidebarProps) => {
    const [favorites, setFavorites] = useState<Set<string>>(() => loadFavorites());
    const [isTopicExpanded, setIsTopicExpanded] = useState(true);
    const [isSourceExpanded, setIsSourceExpanded] = useState(false);
    const [isVideoProviderExpanded, setIsVideoProviderExpanded] = useState(true);
    const [isVideoTypeExpanded, setIsVideoTypeExpanded] = useState(true);
    const [isVideoRolloutExpanded, setIsVideoRolloutExpanded] = useState(false);
    const [isVideoTopicExpanded, setIsVideoTopicExpanded] = useState(false);

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
    const hotEventsInRange = events.filter((event) => isEventInTimeRange(event.last_seen_at, timeRange));
    const sourceScopedEvents = selectedSourceTier
      ? hotEventsInRange.filter((event) => event.source_tier === selectedSourceTier)
      : hotEventsInRange;
    const filteredEvents = activeTab === 'favorites'
      ? events.filter((event) => favorites.has(event.id))
      : sourceScopedEvents.filter((event) => {
        if (selectedTags.length === 0) return true;
        const eventTags = event.tags?.map((tag) => tag.trim().toLowerCase()) ?? [];
        return selectedTags.every((tag) => eventTags.includes(tag));
      });

    const tagCounts = sourceScopedEvents.reduce<Record<string, number>>((acc, event) => {
      for (const tag of event.tags ?? []) {
        acc[tag] = (acc[tag] ?? 0) + 1;
      }
      return acc;
    }, {});

    const visibleTagOptions = TOPIC_TAG_OPTIONS.filter(
      ({ value }) => selectedTags.includes(value) || (tagCounts[value] ?? 0) > 0
    );

    const favCount = favorites.size;
    const tierCounts = hotEventsInRange.reduce<Record<string, number>>((acc, event) => {
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
            onClick={() => onTabChange('hot')}
          >
            News
          </button>
          <button
            type="button"
            className={`sidebar-tab ${activeTab === 'video' ? 'active' : ''}`}
            onClick={() => onTabChange('video')}
          >
            Live
          </button>
          <button
            type="button"
            className={`sidebar-tab ${activeTab === 'favorites' ? 'active' : ''}`}
            onClick={() => onTabChange('favorites')}
          >
            Favorites
            {favCount > 0 && <span className="tab-badge">{favCount}</span>}
          </button>
        </div>

        {activeTab === 'hot' && (
          <>
            <div className="time-filters">
              {(['today', 'yesterday', '3days'] as NewsTimeRange[]).map((range) => (
                <button
                  key={range}
                  type="button"
                  className={`time-btn ${timeRange === range ? 'active' : ''}`}
                  onClick={() => onTimeRangeChange(range)}
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

        {activeTab === 'video' && (
          <>
            <div className="filter-section">
              <button
                type="button"
                className="filter-section-toggle"
                onClick={() => setIsVideoProviderExpanded((prev) => !prev)}
                aria-expanded={isVideoProviderExpanded}
              >
                <span className={`filter-section-arrow ${isVideoProviderExpanded ? 'expanded' : ''}`} aria-hidden />
                <span className="filter-section-title">Providers</span>
              </button>
              <div className={`filter-section-body ${isVideoProviderExpanded ? 'expanded' : ''}`}>
                <div className="filter-chip-grid">
                  {VIDEO_PROVIDER_OPTIONS.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      className={`source-chip ${videoProvider === value ? 'active' : ''}`}
                      onClick={() => onVideoProviderChange(value)}
                    >
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="filter-section">
              <button
                type="button"
                className="filter-section-toggle"
                onClick={() => setIsVideoTypeExpanded((prev) => !prev)}
                aria-expanded={isVideoTypeExpanded}
              >
                <span className={`filter-section-arrow ${isVideoTypeExpanded ? 'expanded' : ''}`} aria-hidden />
                <span className="filter-section-title">Video Type</span>
              </button>
              <div className={`filter-section-body ${isVideoTypeExpanded ? 'expanded' : ''}`}>
                <div className="filter-chip-grid">
                  {VIDEO_TYPE_OPTIONS.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      className={`source-chip ${videoType === value ? 'active' : ''}`}
                      onClick={() => onVideoTypeChange(value)}
                    >
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="filter-section">
              <button
                type="button"
                className="filter-section-toggle"
                onClick={() => setIsVideoRolloutExpanded((prev) => !prev)}
                aria-expanded={isVideoRolloutExpanded}
              >
                <span className={`filter-section-arrow ${isVideoRolloutExpanded ? 'expanded' : ''}`} aria-hidden />
                <span className="filter-section-title">Rollout</span>
              </button>
              <div className={`filter-section-body ${isVideoRolloutExpanded ? 'expanded' : ''}`}>
                <div className="filter-chip-grid">
                  {VIDEO_ROLLOUT_OPTIONS.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      className={`source-chip ${videoRolloutState === value ? 'active' : ''}`}
                      onClick={() => onVideoRolloutStateChange(value)}
                    >
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="filter-section">
              <button
                type="button"
                className="filter-section-toggle"
                onClick={() => setIsVideoTopicExpanded((prev) => !prev)}
                aria-expanded={isVideoTopicExpanded}
              >
                <span className={`filter-section-arrow ${isVideoTopicExpanded ? 'expanded' : ''}`} aria-hidden />
                <span className="filter-section-title">Topics</span>
              </button>
              <div className={`filter-section-body ${isVideoTopicExpanded ? 'expanded' : ''}`}>
                <div className="filter-chip-grid">
                  {VIDEO_TOPIC_OPTIONS.map(({ value, label }) => (
                    <button
                      key={value ?? 'all'}
                      type="button"
                      className={`topic-chip ${videoTopic === value ? 'active' : ''}`}
                      onClick={() => onVideoTopicChange(value)}
                    >
                      <span>{label}</span>
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
          {activeTab === 'video' && <h2 className="sidebar-title">Live Feed</h2>}
          {activeTab !== 'video' && (
            <span className="sidebar-count">{filteredEvents.length} events</span>
          )}
        </div>

        <div className="sidebar-list">
          {activeTab === 'video' ? (
            <LiveVideos
              provider={videoProvider}
              videoType={videoType}
              rolloutState={videoRolloutState}
              topic={videoTopic}
              variant="sidebar"
            />
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
                  <span className="item-time">{formatRelativeTime(event.last_seen_at, now)}</span>
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
