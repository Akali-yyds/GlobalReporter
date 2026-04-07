import { useEffect, useMemo, useRef, useState } from 'react';
import type { VideoSource } from '../../types/video';

interface YouTubeEmbedPlayerProps {
  source: VideoSource;
  active: boolean;
}

function buildEmbedUrl(source: VideoSource): string | null {
  if (!source.embed_url) return null;
  const separator = source.embed_url.includes('?') ? '&' : '?';
  return `${source.embed_url}${separator}autoplay=1&mute=1&playsinline=1&rel=0`;
}

export default function YouTubeEmbedPlayer({ source, active }: YouTubeEmbedPlayerProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [pageVisible, setPageVisible] = useState(document.visibilityState === 'visible');
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => setIsVisible(entry.isIntersecting),
      { rootMargin: '200px 0px' }
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const handleVisibility = () => setPageVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  const shouldRenderPlayer = active && isVisible && pageVisible && source.status !== 'offline' && source.status !== 'error';
  const embedUrl = useMemo(() => buildEmbedUrl(source), [source]);

  useEffect(() => {
    if (!shouldRenderPlayer) {
      setLoaded(false);
    }
  }, [shouldRenderPlayer]);

  return (
    <div className="video-player-shell" ref={containerRef}>
      {shouldRenderPlayer && embedUrl ? (
        <>
          {!loaded && <div className="video-player-state">Loading stream…</div>}
          <iframe
            title={source.display_name}
            src={embedUrl}
            className={`video-player-frame ${loaded ? 'is-ready' : 'is-loading'}`}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            onLoad={() => setLoaded(true)}
          />
        </>
      ) : (
        <div className={`video-player-state video-player-state--${source.status}`}>
          {source.status === 'offline' ? 'Stream offline' : source.status === 'error' ? 'Probe error' : 'Ready to play'}
        </div>
      )}
    </div>
  );
}
