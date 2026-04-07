import { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';
import type { VideoSource } from '../../types/video';

interface HlsVideoPlayerProps {
  source: VideoSource;
  active: boolean;
}

export default function HlsVideoPlayer({ source, active }: HlsVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [pageVisible, setPageVisible] = useState(document.visibilityState === 'visible');

  useEffect(() => {
    const handleVisibility = () => setPageVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !source.playback_url || !active || !pageVisible) {
      return;
    }

    setError(null);
    setReady(false);

    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = source.playback_url;
      video.muted = true;
      video.playsInline = true;
      video.play().catch(() => {});
      const onLoadedData = () => setReady(true);
      const onError = () => setError('Unable to play HLS source');
      video.addEventListener('loadeddata', onLoadedData);
      video.addEventListener('error', onError);
      return () => {
        video.pause();
        video.removeAttribute('src');
        video.load();
        video.removeEventListener('loadeddata', onLoadedData);
        video.removeEventListener('error', onError);
      };
    }

    if (!Hls.isSupported()) {
      setError('HLS not supported in this browser');
      return;
    }

    const hls = new Hls({
      autoStartLoad: true,
      enableWorker: true,
      lowLatencyMode: true,
    });
    hls.loadSource(source.playback_url);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      setReady(true);
      video.muted = true;
      video.playsInline = true;
      video.play().catch(() => {});
    });
    hls.on(Hls.Events.ERROR, (_event, data) => {
      if (data.fatal) {
        setError(data.details || 'Fatal HLS error');
      }
    });

    return () => {
      video.pause();
      hls.destroy();
    };
  }, [source.playback_url, active, pageVisible]);

  if (source.status === 'offline') {
    return <div className="video-player-state video-player-state--offline">Stream offline</div>;
  }

  if (source.status === 'error' && !active) {
    return <div className="video-player-state video-player-state--error">Probe error</div>;
  }

  return (
    <div className="video-player-shell">
      {!ready && !error && <div className="video-player-state">Loading stream…</div>}
      {error && <div className="video-player-state video-player-state--error">{error}</div>}
      <video
        ref={videoRef}
        className={`video-player-frame ${ready ? 'is-ready' : 'is-loading'}`}
        controls
        muted
        playsInline
      />
    </div>
  );
}
