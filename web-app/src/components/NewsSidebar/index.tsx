import { memo, useState, useEffect, useCallback } from 'react';
import type { NewsEvent } from '../../types/news';
import './NewsSidebar.css';

export type TimeRange = 'today' | 'yesterday' | '3days';

interface NewsSidebarProps {
  events: NewsEvent[];
  /** Ignored — count is computed from filtered events internally */
  total?: number;
  selectedEventId?: string;
  onEventClick: (eventId: string) => void;
}

const FAVORITES_KEY = 'ainewser.favorites';

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
  } catch {}
}

const NewsSidebar = memo(
  ({ events, total: _total, selectedEventId, onEventClick }: NewsSidebarProps) => {
    const [activeTab, setActiveTab] = useState<'hot' | 'favorites' | 'video'>('hot');
    const [timeRange, setTimeRange] = useState<TimeRange>('today');
    const [favorites, setFavorites] = useState<Set<string>>(() => loadFavorites());

    // Expose toggleFavorite so parent/detail panel can update
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
      const ONE_DAY = 24 * 60 * 60 * 1000;
      const diff = now - new Date(isoString).getTime();
      // 过去三天 = yesterday ~ 3 days ago (NOT today, NOT beyond 3 days)
      return diff >= ONE_DAY && diff <= 3 * ONE_DAY;
    }, [now]);

    const filteredEvents = events.filter((e) => {
      if (activeTab === 'favorites') return favorites.has(e.id);
      if (activeTab === 'hot') {
        switch (timeRange) {
          case 'today': return isToday(e.first_seen_at);
          case 'yesterday': return isYesterday(e.first_seen_at);
          case '3days': return isWithin3Days(e.first_seen_at);
        }
      }
      return true;
    });

    const formatTime = (isoString: string) => {
      const date = new Date(isoString);
      const diff = now - date.getTime();
      const hours = Math.floor(diff / (1000 * 60 * 60));
      if (hours < 1) return '刚刚';
      if (hours < 24) return `${hours}小时前`;
      const days = Math.floor(hours / 24);
      if (days < 7) return `${days}天前`;
      return date.toLocaleDateString('zh-CN');
    };

    const favCount = favorites.size;

    return (
      <div className="news-sidebar">
        {/* Tab bar */}
        <div className="sidebar-tabs">
          <button
            type="button"
            className={`sidebar-tab ${activeTab === 'hot' ? 'active' : ''}`}
            onClick={() => setActiveTab('hot')}
          >
            热点新闻
          </button>
          <button
            type="button"
            className={`sidebar-tab ${activeTab === 'favorites' ? 'active' : ''}`}
            onClick={() => setActiveTab('favorites')}
          >
            收藏夹
            {favCount > 0 && <span className="tab-badge">{favCount}</span>}
          </button>
          <button
            type="button"
            className={`sidebar-tab ${activeTab === 'video' ? 'active' : ''}`}
            onClick={() => setActiveTab('video')}
          >
            视频流
          </button>
        </div>

        {/* Hot news: time filters */}
        {activeTab === 'hot' && (
          <div className="time-filters">
            {(['today', 'yesterday', '3days'] as TimeRange[]).map((r) => (
              <button
                key={r}
                type="button"
                className={`time-btn ${timeRange === r ? 'active' : ''}`}
                onClick={() => setTimeRange(r)}
              >
                {r === 'today' ? '今日' : r === 'yesterday' ? '昨日' : '过去三天'}
              </button>
            ))}
          </div>
        )}

        {/* Header */}
        <div className="sidebar-header">
          {activeTab === 'hot' && (
            <h2 className="sidebar-title">
              {timeRange === 'today' ? '今日' : timeRange === 'yesterday' ? '昨日' : '近三天'}
            </h2>
          )}
          {activeTab === 'favorites' && <h2 className="sidebar-title">收藏夹</h2>}
          {activeTab === 'video' && <h2 className="sidebar-title">视频流</h2>}
          {activeTab !== 'video' && (
            <span className="sidebar-count">{filteredEvents.length} 条</span>
          )}
        </div>

        {/* Content */}
        <div className="sidebar-list">
          {activeTab === 'video' ? (
            <div className="sidebar-video-placeholder">
              <div className="video-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              </div>
              <p className="video-title">新闻视频流</p>
              <p className="video-subtitle">即将上线，敬请期待</p>
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="sidebar-empty">
              <p>{activeTab === 'favorites' ? '暂无收藏' : '暂无热点新闻'}</p>
            </div>
          ) : (
            filteredEvents.map((event) => (
              <div
                key={event.id}
                className={`sidebar-item ${selectedEventId === event.id ? 'selected' : ''}`}
                onClick={() => onEventClick(event.id)}
              >
                <div className="item-header">
                  <span className="item-country">{event.main_country || '未知'}</span>
                  <span className="item-time">{formatTime(event.first_seen_at)}</span>
                </div>
                <h3 className="item-title">{event.title}</h3>
                <div className="item-footer">
                  <span className="item-heat">热度 {event.heat_score}</span>
                  <span className="item-articles">{event.article_count} 篇</span>
                  {favorites.has(event.id) && (
                    <span className="item-star favorited" title="已收藏">★</span>
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
