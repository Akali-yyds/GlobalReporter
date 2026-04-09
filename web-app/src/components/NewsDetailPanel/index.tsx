import { memo, useEffect, useMemo, useState } from 'react';
import type { NewsEvent, Hotspot } from '../../types/news';
import { newsApi } from '../../services/api';
import './NewsDetailPanel.css';

interface NewsDetailPanelProps {
  event: NewsEvent | null;
  isOpen: boolean;
  onClose: () => void;
  onBack?: () => void;
  regionHotspots?: Hotspot[] | null;
  regionTotal?: number | null;
  regionName?: string | null;
  onRegionHotspotClick?: (eventId: string) => void;
}

function toggleFavorite(eventId: string, favorited: boolean) {
  window.dispatchEvent(new CustomEvent('favorite-toggle', { detail: { eventId, favorited } }));
}

function isFavorited(eventId: string): boolean {
  try {
    const raw = localStorage.getItem('ainewser.favorites');
    if (!raw) return false;
    const values = JSON.parse(raw) as string[];
    return values.includes(eventId);
  } catch {
    return false;
  }
}

const NewsDetailPanel = memo(
  ({
    event,
    isOpen,
    onClose,
    onBack,
    regionHotspots,
    regionTotal,
    regionName,
    onRegionHotspotClick,
  }: NewsDetailPanelProps) => {
    const [detail, setDetail] = useState<NewsEvent | null>(null);
    const [loading, setLoading] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [favorited, setFavorited] = useState(false);

    const uniqueRegionHotspots = useMemo(() => {
      if (regionHotspots == null) return null;

      const unique = new Map<string, Hotspot>();
      regionHotspots.forEach((hotspot, index) => {
        const key = hotspot.event_id || `${hotspot.geo_key || 'geo'}-${index}`;
        const existing = unique.get(key);
        if (!existing || hotspot.heat_score > existing.heat_score) {
          unique.set(key, hotspot);
        }
      });

      return Array.from(unique.values());
    }, [regionHotspots]);

    useEffect(() => {
      if (!isOpen || !event) {
        setDetail(null);
        setLoadError(null);
        setFavorited(false);
        return;
      }

      let cancelled = false;
      setLoading(true);
      setLoadError(null);
      setDetail(event);
      setFavorited(isFavorited(event.id));

      newsApi
        .getNewsDetail(event.id)
        .then((data) => {
          if (!cancelled) setDetail(data as unknown as NewsEvent);
        })
        .catch(() => {
          if (!cancelled) setLoadError('加载详情失败');
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });

      return () => {
        cancelled = true;
      };
    }, [isOpen, event?.id]);

    if (!isOpen) return null;

    if (uniqueRegionHotspots != null) {
      return (
        <div className="news-detail-panel">
          <div className="detail-header">
            <h2 className="detail-title">{regionName || '地区新闻'}</h2>
            <div className="detail-header-actions">
              {onBack && (
                <button className="detail-back" onClick={onBack} aria-label="返回上级">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M19 12H5M12 5l-7 7 7 7" />
                  </svg>
                </button>
              )}
              <button className="detail-close" onClick={onClose} aria-label="关闭">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <div className="detail-content">
            {uniqueRegionHotspots.length === 0 ? (
              <p className="detail-loading">该地区暂无热点新闻</p>
            ) : (
              <>
                <div className="region-news-count">{regionTotal ?? uniqueRegionHotspots.length} news</div>
                <ul className="region-news-list">
                  {uniqueRegionHotspots.map((hotspot, index) => (
                    <li
                      key={hotspot.event_id || `${hotspot.geo_key || 'geo'}-${index}`}
                      className="region-news-item"
                      onClick={() => onRegionHotspotClick?.(hotspot.event_id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => e.key === 'Enter' && onRegionHotspotClick?.(hotspot.event_id)}
                    >
                      <div className="region-news-meta">
                        <span className="region-news-heat">热度 {hotspot.heat_score}</span>
                        {hotspot.geo_name && <span className="region-news-geo">{hotspot.geo_name}</span>}
                      </div>
                      <span className="region-news-title">{hotspot.title}</span>
                      {hotspot.summary && <span className="region-news-summary">{hotspot.summary}</span>}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      );
    }

    if (!event) return null;

    const resolved = detail ?? event;
    const articleUrl = resolved.primary_article_url?.trim();
    const channelLabel = resolved.primary_source_name || resolved.primary_source_code || '未知渠道';

    const openOriginal = () => {
      if (articleUrl) {
        window.open(articleUrl, '_blank', 'noopener,noreferrer');
      }
    };

    const handleFavoriteToggle = () => {
      const next = !favorited;
      setFavorited(next);
      toggleFavorite(resolved.id, next);
    };

    return (
      <div className="news-detail-panel">
        <div className="detail-header">
          <h2 className="detail-title">新闻详情</h2>
          <div className="detail-header-actions">
            <button
              type="button"
              className={`favorite-btn ${favorited ? 'active' : ''}`}
              onClick={handleFavoriteToggle}
              title={favorited ? '取消收藏' : '收藏新闻'}
              aria-label={favorited ? '取消收藏' : '收藏新闻'}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill={favorited ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
            </button>
            <button className="detail-close" onClick={onClose} aria-label="关闭">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="detail-content">
          {loadError && <p className="detail-inline-error">{loadError}</p>}
          {loading && <p className="detail-loading">加载中...</p>}

          <article className="detail-article">
            <h1 className="article-title">{resolved.title}</h1>

            <div className="article-channel" title="新闻来源渠道">
              <span className="channel-label">渠道</span>
              <span className="channel-value">{channelLabel}</span>
              {resolved.primary_source_code && resolved.primary_source_name && (
                <span className="channel-code">({resolved.primary_source_code})</span>
              )}
            </div>

            <div className="article-meta">
              <span className="meta-country">{resolved.main_country || '未知地区'}</span>
              <span className="meta-separator">|</span>
              <span className="meta-heat">热度: {resolved.heat_score}</span>
              <span className="meta-separator">|</span>
              <span className="meta-articles">{resolved.article_count} 篇相关报道</span>
            </div>

            <div className="article-summary">
              <h3>摘要</h3>
              <p>{resolved.summary || '暂无摘要'}</p>
            </div>

            <div className="article-regions">
              <h3>涉及地区</h3>
              <div className="region-tags">
                {resolved.geo_mappings?.map((mapping) => {
                  const label = mapping.geo_name || mapping.matched_text || mapping.geo_key;
                  const geoType =
                    mapping.geo_type ||
                    (mapping.display_type?.includes('country')
                      ? 'country'
                      : mapping.display_type?.includes('city')
                        ? 'city'
                        : 'admin1');
                  const typeLabel = geoType === 'country' ? '国' : geoType === 'city' ? '市' : '省';
                  const precisionHint = mapping.display_type ? ` · ${mapping.display_type}` : '';
                  return (
                    <span
                      key={mapping.id}
                      className={`region-tag region-tag--${geoType}${mapping.is_primary ? ' region-tag--primary' : ''}`}
                      title={`来源: ${mapping.matched_text || '-'} · 置信度 ${(mapping.confidence * 100).toFixed(0)}%${precisionHint}`}
                    >
                      <span className="region-tag-type">{typeLabel}</span>
                      {label}
                      {mapping.is_primary && <span className="region-tag-primary-dot" />}
                    </span>
                  );
                })}
                {(!resolved.geo_mappings || resolved.geo_mappings.length === 0) && (
                  <span className="no-region">暂无地区信息</span>
                )}
              </div>
            </div>

            {resolved.related_sources && resolved.related_sources.length > 1 && (
              <div className="article-sources-list">
                <h3>报道来源</h3>
                <ul>
                  {resolved.related_sources.map((source) => (
                    <li key={`${source.source_code}-${source.article_url}`}>
                      <button
                        type="button"
                        className="source-link"
                        onClick={() => window.open(source.article_url, '_blank', 'noopener,noreferrer')}
                      >
                        {source.source_name}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="article-actions">
              <button
                type="button"
                className="action-btn primary"
                disabled={!articleUrl}
                onClick={openOriginal}
                title={articleUrl || '暂无原文链接'}
              >
                查看原文
              </button>
              <button
                type="button"
                className="action-btn secondary"
                onClick={() => {
                  if (articleUrl && navigator.clipboard?.writeText) {
                    void navigator.clipboard.writeText(articleUrl);
                  }
                }}
                disabled={!articleUrl}
              >
                复制链接
              </button>
            </div>
          </article>
        </div>
      </div>
    );
  }
);

NewsDetailPanel.displayName = 'NewsDetailPanel';

export default NewsDetailPanel;
