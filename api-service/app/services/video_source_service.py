"""Video source seed and query helpers."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.models import VideoJobProfile, VideoSource


VIDEO_SEED_SOURCES: list[dict] = [
    {
        "source_code": "sky_news_live",
        "display_name": "Sky News Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UCkFclpi8U9VJjfxLYoms7Aw",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UCkFclpi8U9VJjfxLYoms7Aw",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "Sky News Live",
        "description": "Continuous live coverage from Sky News.",
        "region": "Europe",
        "country": "United Kingdom",
        "city": "London",
        "topic_tags": ["news", "live", "europe"],
        "license_mode": "youtube_embed",
        "priority": 20,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {"channel_url": "https://www.youtube.com/@SkyNews"},
    },
    {
        "source_code": "dw_live",
        "display_name": "DW News Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UCbbS1GE942k3UVqpLklyhIA",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UCbbS1GE942k3UVqpLklyhIA",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "DW News Live",
        "description": "Official DW global live channel.",
        "region": "Europe",
        "country": "Germany",
        "city": "Berlin",
        "topic_tags": ["news", "live", "europe"],
        "license_mode": "youtube_embed",
        "priority": 21,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {"channel_url": "https://www.youtube.com/@DWNews"},
    },
    {
        "source_code": "aljazeera_live",
        "display_name": "Al Jazeera English Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UCfiwzLy-8yKzIbsmZTzxDgw",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UCfiwzLy-8yKzIbsmZTzxDgw",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "Al Jazeera English Live",
        "description": "Official Al Jazeera English live stream.",
        "region": "Middle East",
        "country": "Qatar",
        "city": "Doha",
        "topic_tags": ["news", "live", "middle-east"],
        "license_mode": "youtube_embed",
        "priority": 1,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {"channel_url": "https://www.youtube.com/@aljazeeraenglish"},
    },
    {
        "source_code": "abc_news_live",
        "display_name": "ABC News Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UCBi2mrWuNuyYy4gbM6fU18Q",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UCBi2mrWuNuyYy4gbM6fU18Q",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "ABC News Live",
        "description": "ABC News Live 24/7 streaming news channel via official YouTube embed.",
        "region": "North America",
        "country": "United States",
        "city": "New York",
        "topic_tags": ["news", "live", "breaking", "north-america"],
        "license_mode": "youtube_embed",
        "priority": 10,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {
            "channel_url": "https://www.youtube.com/@ABCNews",
            "homepage": "https://abcnews.go.com/Live",
        },
    },
    {
        "source_code": "france24_en_live",
        "display_name": "FRANCE 24 English Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UCQfwfsi5VrQ8yKZ-UWmAEFg",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UCQfwfsi5VrQ8yKZ-UWmAEFg",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "FRANCE 24 English Live",
        "description": "FRANCE 24 English international news 24/7 via official YouTube embed.",
        "region": "Europe",
        "country": "France",
        "city": "Paris",
        "topic_tags": ["news", "live", "europe", "international"],
        "license_mode": "youtube_embed",
        "priority": 11,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {
            "channel_url": "https://www.youtube.com/@France24_en",
            "homepage": "https://www.france24.com/en/live",
        },
    },
    {
        "source_code": "euronews_live",
        "display_name": "Euronews English Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UCSrZ3UV4jOidv8ppoVuvW9Q",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UCSrZ3UV4jOidv8ppoVuvW9Q",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "Euronews English Live",
        "description": "Euronews live coverage via official YouTube embed.",
        "region": "Europe",
        "country": "France",
        "city": "Lyon",
        "topic_tags": ["news", "live", "europe", "eu"],
        "license_mode": "youtube_embed",
        "priority": 12,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {
            "channel_url": "https://www.youtube.com/@euronews",
            "homepage": "https://www.euronews.com/live",
        },
    },
    {
        "source_code": "cna_live",
        "display_name": "CNA 24/7 Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UC83jt4dlz1Gjl58fzQrrKZg",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UC83jt4dlz1Gjl58fzQrrKZg",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "CNA 24/7 Live",
        "description": "Channel NewsAsia 24/7 live breaking news via official YouTube embed.",
        "region": "Asia",
        "country": "Singapore",
        "city": "Singapore",
        "topic_tags": ["news", "live", "asia", "breaking"],
        "license_mode": "youtube_embed",
        "priority": 13,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {
            "channel_url": "https://www.youtube.com/channelnewsasia",
            "homepage": "https://www.channelnewsasia.com/watch",
        },
    },
    {
        "source_code": "nhk_world_live",
        "display_name": "NHK WORLD-JAPAN Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UCSPEjw8F2nQDtmUKPFNF7_A",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UCSPEjw8F2nQDtmUKPFNF7_A",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "NHK WORLD-JAPAN Live",
        "description": "NHK WORLD-JAPAN live news from Japan, Asia and the world.",
        "region": "Asia",
        "country": "Japan",
        "city": "Tokyo",
        "topic_tags": ["news", "live", "asia", "japan"],
        "license_mode": "youtube_embed",
        "priority": 14,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {
            "channel_url": "https://www.youtube.com/@NHKWORLDJAPAN",
            "homepage": "https://www3.nhk.or.jp/nhkworld/en/live/",
        },
    },
    {
        "source_code": "bloomberg_live",
        "display_name": "Bloomberg Television Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UCyxnPZfofoutjmyvaV0GGeQ",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UCyxnPZfofoutjmyvaV0GGeQ",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "Bloomberg TV Live",
        "description": "Official Bloomberg Television live stream.",
        "region": "North America",
        "country": "United States",
        "city": "New York",
        "topic_tags": ["news", "finance", "live"],
        "license_mode": "youtube_embed",
        "priority": 22,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {"channel_url": "https://www.youtube.com/@BloombergTelevision"},
    },
    {
        "source_code": "pbs_newshour_live",
        "display_name": "PBS NewsHour Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UC2s0uKOc2WgB9eGta7cUUEA",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UC2s0uKOc2WgB9eGta7cUUEA",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "PBS NewsHour Live",
        "description": "Official PBS NewsHour live coverage.",
        "region": "North America",
        "country": "United States",
        "city": "Washington, D.C.",
        "topic_tags": ["news", "public-media", "live"],
        "license_mode": "youtube_embed",
        "priority": 23,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {"channel_url": "https://www.youtube.com/@PBSNewsHour"},
    },
    {
        "source_code": "nbc_news_live",
        "display_name": "NBC News Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UChDKyKQ59fYz3JO2fl0Z6sg",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UChDKyKQ59fYz3JO2fl0Z6sg",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "NBC News Live",
        "description": "Official NBC News live stream.",
        "region": "North America",
        "country": "United States",
        "city": "New York",
        "topic_tags": ["news", "live", "breaking"],
        "license_mode": "youtube_embed",
        "priority": 24,
        "enabled": True,
        "rollout_state": "canary",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {"channel_url": "https://www.youtube.com/@NBCNews"},
    },
    {
        "source_code": "cbs_news_live",
        "display_name": "CBS News Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UC-SJ6nODDmufqBzPBwCvYvQ",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UC-SJ6nODDmufqBzPBwCvYvQ",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "CBS News Live",
        "description": "Official CBS News live stream.",
        "region": "North America",
        "country": "United States",
        "city": "New York",
        "topic_tags": ["news", "live", "breaking"],
        "license_mode": "youtube_embed",
        "priority": 25,
        "enabled": True,
        "rollout_state": "canary",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {"channel_url": "https://www.youtube.com/@CBSNews"},
    },
    {
        "source_code": "fox_news_live",
        "display_name": "Fox News Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UCqlYzSgsh5jdtWYfVIBoTDw",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UCqlYzSgsh5jdtWYfVIBoTDw",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "Fox News Live",
        "description": "Official Fox News live stream.",
        "region": "North America",
        "country": "United States",
        "city": "New York",
        "topic_tags": ["news", "live", "breaking"],
        "license_mode": "youtube_embed",
        "priority": 26,
        "enabled": True,
        "rollout_state": "poc",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {"channel_url": "https://www.youtube.com/@FoxNews"},
    },
    {
        "source_code": "nasa_live",
        "display_name": "NASA Live",
        "video_type": "youtube_embed",
        "provider": "youtube",
        "channel_or_stream_id": "UC9SM7V7J1pAhPabOUST01fw",
        "embed_url": "https://www.youtube.com/embed/live_stream?channel=UC9SM7V7J1pAhPabOUST01fw",
        "thumbnail_url": "https://i.ytimg.com/vi_webp/live_stream/default/live.jpg",
        "title": "NASA Live",
        "description": "Official NASA public live stream.",
        "region": "North America",
        "country": "United States",
        "city": "Washington, D.C.",
        "topic_tags": ["space", "official", "live"],
        "license_mode": "youtube_embed",
        "priority": 27,
        "enabled": True,
        "rollout_state": "canary",
        "status": "unknown",
        "notes": "Official YouTube live embed.",
        "source_metadata": {"channel_url": "https://www.youtube.com/@NASA"},
    },
    {
        "source_code": "wusa9_hls",
        "display_name": "WUSA9 HLS Live",
        "video_type": "hls",
        "provider": "direct_hls",
        "channel_or_stream_id": "wusa9-live",
        "playback_url": "https://livevideo01.wusa9.com/hls/live/2015498/newscasts/live.m3u8",
        "title": "WUSA9 Live Stream",
        "description": "Direct HLS live stream.",
        "region": "North America",
        "country": "United States",
        "city": "Washington, D.C.",
        "topic_tags": ["news", "hls", "live"],
        "license_mode": "public_stream",
        "priority": 2,
        "enabled": True,
        "rollout_state": "default",
        "status": "unknown",
        "notes": "Stable direct HLS live stream.",
        "source_metadata": {"homepage": "https://www.wusa9.com/watch"},
    },
    {
        "source_code": "global_news_hls",
        "display_name": "Global News HLS",
        "video_type": "hls",
        "provider": "direct_hls",
        "channel_or_stream_id": "global-news-live",
        "playback_url": "https://live.corusdigitaldev.com/groupd/live/49a91e7f-1023-430f-8d66-561055f3d0f7/live.isml/.m3u8",
        "title": "Global News Live",
        "description": "Direct HLS live stream.",
        "region": "North America",
        "country": "Canada",
        "city": "Toronto",
        "topic_tags": ["news", "hls", "live"],
        "license_mode": "public_stream",
        "priority": 3,
        "enabled": True,
        "rollout_state": "canary",
        "status": "unknown",
        "notes": "Stable direct HLS live stream.",
        "source_metadata": {"homepage": "https://globalnews.ca/live/national/"},
    },
]


VIDEO_JOB_PROFILES: list[dict] = [
    {
        "job_code": "video_probe_realtime",
        "job_mode": "realtime",
        "rollout_state": "default",
        "enabled": True,
        "interval_minutes": 10,
        "max_sources": 12,
        "notes": "Probe default rollout video sources frequently.",
    },
    {
        "job_code": "video_probe_canary",
        "job_mode": "realtime",
        "rollout_state": "canary",
        "enabled": True,
        "interval_minutes": 30,
        "max_sources": 8,
        "notes": "Probe canary video sources with lower frequency.",
    },
    {
        "job_code": "video_probe_backfill",
        "job_mode": "backfill",
        "rollout_state": "poc",
        "enabled": True,
        "interval_minutes": 360,
        "max_sources": 20,
        "notes": "Probe poc and draft video sources in low frequency sweeps.",
    },
]


def _normalize_tags(value: Iterable[str] | None) -> list[str]:
    if not value:
        return []
    return sorted({str(tag).strip().lower() for tag in value if str(tag).strip()})


def ensure_video_seed_data(db: Session) -> None:
    """Ensure default video source rows and job profiles exist."""

    for seed in VIDEO_SEED_SOURCES:
        source = db.query(VideoSource).filter(VideoSource.source_code == seed["source_code"]).first()
        normalized_tags = _normalize_tags(seed.get("topic_tags"))
        if source is None:
            source = VideoSource(
                source_code=seed["source_code"],
                display_name=seed["display_name"],
                video_type=seed["video_type"],
                provider=seed["provider"],
                channel_or_stream_id=seed.get("channel_or_stream_id"),
                embed_url=seed.get("embed_url"),
                playback_url=seed.get("playback_url"),
                thumbnail_url=seed.get("thumbnail_url"),
                title=seed.get("title"),
                description=seed.get("description"),
                region=seed.get("region"),
                country=seed.get("country"),
                city=seed.get("city"),
                topic_tags=normalized_tags,
                license_mode=seed.get("license_mode", "public_embed"),
                priority=seed.get("priority", 100),
                enabled=seed.get("enabled", True),
                rollout_state=seed.get("rollout_state", "draft"),
                status=seed.get("status", "unknown"),
                notes=seed.get("notes"),
                source_metadata=seed.get("source_metadata") or {},
            )
            db.add(source)
        else:
            source.display_name = seed["display_name"]
            source.video_type = seed["video_type"]
            source.provider = seed["provider"]
            source.channel_or_stream_id = seed.get("channel_or_stream_id")
            source.embed_url = seed.get("embed_url")
            source.playback_url = seed.get("playback_url")
            source.region = seed.get("region")
            source.country = seed.get("country")
            source.city = seed.get("city")
            source.topic_tags = normalized_tags
            source.license_mode = seed.get("license_mode", source.license_mode)
            source.priority = seed.get("priority", source.priority)
            source.source_metadata = seed.get("source_metadata") or {}
            source.notes = seed.get("notes")
            source.enabled = seed.get("enabled", True)
            source.rollout_state = seed.get("rollout_state", source.rollout_state)
            if not source.title:
                source.title = seed.get("title")
            if not source.description:
                source.description = seed.get("description")
            if not source.thumbnail_url:
                source.thumbnail_url = seed.get("thumbnail_url")

    for profile_seed in VIDEO_JOB_PROFILES:
        profile = db.query(VideoJobProfile).filter(VideoJobProfile.job_code == profile_seed["job_code"]).first()
        if profile is None:
            profile = VideoJobProfile(**profile_seed)
            db.add(profile)
        else:
            profile.job_mode = profile_seed["job_mode"]
            profile.rollout_state = profile_seed["rollout_state"]
            profile.enabled = profile_seed["enabled"]
            profile.interval_minutes = profile_seed["interval_minutes"]
            profile.max_sources = profile_seed["max_sources"]
            profile.notes = profile_seed["notes"]

    db.commit()
