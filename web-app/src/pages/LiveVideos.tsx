import { useEffect, useMemo, useState } from 'react';
import VideoGrid from '../components/video/VideoGrid';
import type { VideoRolloutState, VideoSource, VideoType } from '../types/video';
import { videoApi } from '../services/api';
import HlsVideoPlayer from '../components/video/HlsVideoPlayer';
import YouTubeEmbedPlayer from '../components/video/YouTubeEmbedPlayer';
import './LiveVideos.css';

type ViewMode = 'grid' | 'single';
type LiveVideosVariant = 'page' | 'sidebar';

interface LiveVideosProps {
  provider: 'all' | 'youtube' | 'direct_hls';
  videoType: 'all' | VideoType;
  rolloutState: 'all' | VideoRolloutState;
  topic: string | null;
  variant?: LiveVideosVariant;
}

const USER_VERIFIED_PLAYABLE = ['aljazeera_live', 'wusa9_hls', 'global_news_hls'] as const;

function renderSinglePlayer(source: VideoSource) {
  if (source.video_type === 'youtube_embed') {
    return <YouTubeEmbedPlayer source={source} active />;
  }
  return <HlsVideoPlayer source={source} active />;
}

function sortSources(items: VideoSource[]): VideoSource[] {
  return [...items].sort((a, b) => {
    const aVerified = USER_VERIFIED_PLAYABLE.indexOf(a.source_code as (typeof USER_VERIFIED_PLAYABLE)[number]);
    const bVerified = USER_VERIFIED_PLAYABLE.indexOf(b.source_code as (typeof USER_VERIFIED_PLAYABLE)[number]);
    const aVerifiedRank = aVerified === -1 ? Number.MAX_SAFE_INTEGER : aVerified;
    const bVerifiedRank = bVerified === -1 ? Number.MAX_SAFE_INTEGER : bVerified;
    if (aVerifiedRank !== bVerifiedRank) return aVerifiedRank - bVerifiedRank;

    const statusRank = (source: VideoSource) => {
      if (source.status === 'live') return 0;
      if (source.status === 'unknown') return 1;
      if (source.status === 'offline') return 2;
      return 3;
    };
    const statusDelta = statusRank(a) - statusRank(b);
    if (statusDelta !== 0) return statusDelta;

    if (a.priority !== b.priority) return a.priority - b.priority;
    return (a.display_name || '').localeCompare(b.display_name || '');
  });
}

export default function LiveVideos({
  provider,
  videoType,
  rolloutState,
  topic,
  variant = 'page',
}: LiveVideosProps) {
  const [sources, setSources] = useState<VideoSource[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [selectedSourceCode, setSelectedSourceCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    videoApi.getSources({
      provider: provider === 'all' ? undefined : provider,
      video_type: videoType === 'all' ? undefined : videoType,
      rollout_state: rolloutState === 'all' ? undefined : rolloutState,
      topic: topic ?? undefined,
    })
      .then((data: any) => {
        const items = sortSources(Array.isArray(data) ? data : []);
        setSources(items);
        setSelectedSourceCode((prev) => {
          if (!prev) return items[0]?.source_code ?? null;
          const stillVisible = items.some((item) => item.source_code === prev);
          return stillVisible ? prev : (items[0]?.source_code ?? null);
        });
      })
      .catch(() => setError('Failed to load video sources'))
      .finally(() => setLoading(false));
  }, [provider, rolloutState, topic, videoType]);

  const selectedSource = useMemo(
    () => sources.find((source) => source.source_code === selectedSourceCode) ?? sources[0] ?? null,
    [selectedSourceCode, sources]
  );

  const activeSourceCodes = useMemo(() => {
    if (viewMode === 'single') {
      return selectedSource ? [selectedSource.source_code] : [];
    }
    return sources.slice(0, variant === 'sidebar' ? 3 : 2).map((source) => source.source_code);
  }, [selectedSource, sources, variant, viewMode]);

  return (
    <section className={`video-page ${variant === 'sidebar' ? 'video-page--sidebar' : ''}`}>
      <div className="video-toolbar">
        <div className="video-toolbar-group">
          <button className={viewMode === 'grid' ? 'is-active' : ''} onClick={() => setViewMode('grid')}>
            Grid View
          </button>
          <button className={viewMode === 'single' ? 'is-active' : ''} onClick={() => setViewMode('single')}>
            Single View
          </button>
        </div>
      </div>

      {loading && <div className="video-page-state">Loading live sources...</div>}
      {error && <div className="video-page-state video-page-state--error">{error}</div>}

      {!loading && !error && viewMode === 'grid' && (
        <VideoGrid
          sources={sources}
          selectedSourceCode={selectedSourceCode}
          activeSourceCodes={activeSourceCodes}
          onSelectSource={(source) => setSelectedSourceCode(source.source_code)}
          variant={variant}
        />
      )}

      {!loading && !error && viewMode === 'single' && selectedSource && (
        <div className={`video-single-layout ${variant === 'sidebar' ? 'video-single-layout--sidebar' : ''}`}>
          <div className="video-single-player">
            {renderSinglePlayer(selectedSource)}
            <div className="video-single-meta">
              <h2>{selectedSource.title || selectedSource.display_name}</h2>
              <p>{selectedSource.description || 'No description available.'}</p>
            </div>
          </div>
          <div className="video-single-list">
            {sources.map((source) => (
              <button
                key={source.source_code}
                className={`video-single-list-item ${source.source_code === selectedSource.source_code ? 'is-active' : ''}`}
                onClick={() => setSelectedSourceCode(source.source_code)}
              >
                <span>{source.display_name}</span>
                <span>{source.status}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
