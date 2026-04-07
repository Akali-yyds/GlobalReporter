import type { VideoSource } from '../../types/video';
import HlsVideoPlayer from './HlsVideoPlayer';
import YouTubeEmbedPlayer from './YouTubeEmbedPlayer';

interface VideoGridProps {
  sources: VideoSource[];
  selectedSourceCode: string | null;
  activeSourceCodes: string[];
  onSelectSource: (source: VideoSource) => void;
  variant?: 'page' | 'sidebar';
}

function renderPlayer(source: VideoSource, active: boolean) {
  if (source.video_type === 'youtube_embed') {
    return <YouTubeEmbedPlayer source={source} active={active} />;
  }
  return <HlsVideoPlayer source={source} active={active} />;
}

export default function VideoGrid({
  sources,
  selectedSourceCode,
  activeSourceCodes,
  onSelectSource,
  variant = 'page',
}: VideoGridProps) {
  return (
    <div className={`video-grid ${variant === 'sidebar' ? 'video-grid--sidebar' : ''}`}>
      {sources.map((source) => {
        const location = [source.city, source.country].filter(Boolean).join(' · ') || source.region || 'Unknown region';
        const isSelected = selectedSourceCode === source.source_code;
        return (
          <article
            key={source.source_code}
            className={`video-card ${variant === 'sidebar' ? 'video-card--sidebar' : ''} ${isSelected ? 'is-selected' : ''}`}
            onClick={() => onSelectSource(source)}
          >
            <div className="video-card-player">
              {renderPlayer(source, activeSourceCodes.includes(source.source_code))}
            </div>
            <div className="video-card-body">
              <div className="video-card-topline">
                <span className={`video-card-status video-card-status--${source.status}`}>{source.status}</span>
                <span className="video-card-provider">{source.provider}</span>
              </div>
              <h3 className="video-card-title">{source.title || source.display_name}</h3>
              <p className="video-card-location">{location}</p>
              <p className="video-card-meta">
                Last probe: {source.checkpoint?.last_probe_at ? new Date(source.checkpoint.last_probe_at).toLocaleString() : 'never'}
              </p>
              <div className="video-card-tags">
                {source.topic_tags.slice(0, 4).map((tag) => (
                  <span key={tag} className="video-card-tag">{tag}</span>
                ))}
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
