import { render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, beforeEach, expect } from 'vitest';
import LiveVideos from '../pages/LiveVideos';

vi.mock('../services/api', () => ({
  videoApi: {
    getSources: vi.fn().mockResolvedValue([
      {
        id: '1',
        source_code: 'sky_news_live',
        display_name: 'Sky News Live',
        video_type: 'youtube_embed',
        provider: 'youtube',
        embed_url: 'https://www.youtube.com/embed/live_stream?channel=test',
        playback_url: null,
        thumbnail_url: null,
        title: 'Sky News Live',
        description: 'Test source',
        region: 'Europe',
        country: 'United Kingdom',
        city: 'London',
        topic_tags: ['news'],
        license_mode: 'youtube_embed',
        priority: 1,
        enabled: true,
        rollout_state: 'default',
        status: 'live',
        notes: null,
        source_metadata: {},
        checkpoint: null,
      },
    ]),
  },
}));

describe('LiveVideos', () => {
  beforeEach(() => {
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    });
    class MockIntersectionObserver {
      observe() {}
      disconnect() {}
      unobserve() {}
    }
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
  });

  it('renders video grid after loading', async () => {
    render(
      <LiveVideos
        provider="all"
        videoType="all"
        rolloutState="all"
        topic={null}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Sky News Live')).toBeTruthy();
    });

    expect(screen.getByText('Grid View')).toBeTruthy();
    expect(screen.getByText('Single View')).toBeTruthy();
  });
});
