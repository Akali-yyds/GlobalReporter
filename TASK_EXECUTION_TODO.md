# GlobalReporter TODO Execution Plan

## Context Snapshot

This document is the compressed execution context for the next project phase.

Current system status:

- News is collected by Scrapy spiders from media pages, RSS feeds, and a few hot-topic endpoints.
- The crawler pipeline currently handles text cleaning, deduplication, geo extraction, and ingest.
- The API aggregates articles into `NewsEvent` rows and powers the globe, country heat map, and region drill-down.
- The frontend already supports time-window filtering, country heat coloring, admin1 drill-down, and event detail display.

Current bottlenecks:

- Freshness is not enforced consistently at crawl time.
- High-value news and low-value hot-topic noise are mixed together.
- Social / official-account / community-signal sources are not yet integrated in a structured way.
- Topic tags for frontend filtering are not yet produced in a reliable, normalized way.
- Region extraction is improved, and admin1 coverage now spans the top 50 news countries with multilingual aliases.

## Priority 10

1. Freshness gate
   Enforce source-aware recency rules so crawlers stop ingesting stale articles.

2. High-value content filter
   Down-rank or drop entertainment and low-signal hot topics.

3. Source tiering
   Separate authoritative media, official accounts, social trends, and community signals.

4. Topic tag extraction
   Produce normalized tags such as `technology`, `ai`, `chip`, `conflict`, `earthquake`, `cybersecurity`.

5. Admin1 dictionary expansion
   Extend sub-country geographic coverage beyond `CN / US / JP / GB`.

6. Published-time reliability
   Improve `published_at` extraction completeness and normalize it consistently.

7. Heat-score redesign
   Replace list-position-based heat with multi-factor scoring.

8. Event clustering precision
   Reduce false merges and improve same-event grouping quality.

9. Source quality monitoring
   Track per-source freshness, success rate, low-value ratio, and region extraction yield.

10. Multi-dimensional frontend filtering
    Support time + source tier + tags + geography combinations.

## Execution Phases

### Phase 1: Intake Quality Gate

Goal:

- Reduce stale content
- Reduce low-value content
- Start emitting normalized topic tags

Scope:

- Add freshness filtering in crawler pipeline
- Add first-pass content value classification
- Add first-pass tag extraction and semantic category normalization
- Add focused tests

### Phase 2: Event Semantics

Goal:

- Make aggregated events more meaningful to end users

Scope:

- Event-level tag propagation
- Event-level tag filter support in API
- Better event clustering and similarity controls
- Better heat score design

### Phase 3: Source Expansion

Goal:

- Broaden coverage without flooding noise

Scope:

- Add source tiers
- Add official-account ingestion
- Add social-trend ingestion with separate weighting

### Phase 4: Geo Deepening

Goal:

- Improve region drill-down quality

Scope:

- Expand admin1 dictionaries
- Improve ambiguous city resolution
- Add more admin1 GeoJSON coverage

### Phase 5: Product Filters

Goal:

- Expose the new structure to the frontend

Scope:

- Tag filter API
- Source-tier filter API
- Event-level tag drill-down

## Phase 1 Tasks

### P0

- Add a recency policy module
- Add a content signal / topic tagging module
- Insert a new pipeline stage before deduplication and ingest

### P1

- Drop clearly stale items when `published_at` is older than the configured threshold
- Normalize `published_at` into a stable UTC ISO format when parsing succeeds
- Preserve source-specific flexibility for feeds that still miss `published_at`

### P2

- Detect and drop low-value entertainment-style items
- Keep high-signal categories such as technology, AI, chips, science, conflict, disaster, cybersecurity

### P3

- Emit normalized tags into article payloads
- Normalize coarse category using extracted topic signals

### P4

- Add focused tests for:
  - old-item rejection
  - low-value rejection
  - tag extraction
  - category normalization

## Current Implementation Target

This implementation round starts with Phase 1 and the tag-related slice of Phase 2.

Expected outcome of this round:

- New stale-news filtering is active in crawler intake
- Obvious entertainment / low-value noise is reduced
- Articles begin carrying meaningful normalized tags
- Event `category` becomes more useful for API-side filtering
- Event `tags` are persisted and merged at the aggregated event level
- `/api/news/hot` supports normalized tag filtering
- Frontend sidebar supports topic-tag filtering on the current event feed
- Event clustering no longer relies only on exact normalized-title hashes
- Event heat is recomputed using source diversity, article count, recency, topic, and geo granularity
- Source tiers are persisted on sources and aggregated events
- Source-aware weighting is part of event heat calculation
- Frontend sidebar supports source-tier filtering on the event feed

## Deferred For Later

- Frontend tag bar
- Source-tier UI
- Social platform ingestion adapters
- Admin1 dictionary expansion

## Current Progress

### Done

- Phase 1 crawler intake quality gate
- Event-level tag persistence on `news_events`
- Event-level tag propagation during ingest
- `/api/news/hot?tag=...` backend filtering support
- `/api/news/hot?tags_any=...` and `/api/news/hot?tags_all=...` backend filtering support
- Frontend sidebar tag chips wired to the event feed
- Similar-title event clustering for recent same-country events
- Multi-factor event heat recalculation during ingest
- Source tiers: `official / authoritative / aggregator / community / social`
- `/api/news/hot` and `/api/sources` support source-tier filtering
- Frontend source-tier chips are wired to backend event filtering
- API and crawler regression tests for the new tag flow
- Event clustering now considers geo overlap and source-tier distance
- `/api/sources/analytics` returns tier-level and per-source analytics summaries
- `/api/sources/analytics` now exposes freshness, publish-time coverage, low-signal ratio, tag coverage, and region-yield metrics
- `/api/sources/analytics` now exposes recent crawl counts, success rate, last job status, and latest crawler error
- Official/community adapters added for:
  - NASA RSS
  - OpenAI News RSS
  - Google Blog RSS
  - GitHub Changelog
  - GitHub Releases
  - YouTube official-channel feeds
- Bilibili hot-source filtering is narrowed toward tech / knowledge / current-affairs signals
- Admin1 dictionaries now expand from 4 countries to the project's top 50 news countries
- Admin1 dictionaries now carry multilingual aliases, including broad Chinese coverage for the 50-country set

### Next

- Tighten `bilibili_hot` further around higher-signal subcategories
- Continue official/community source hardening and source-specific freshness behavior
- Add persistent source-health history views and alert thresholds for long-term monitoring
- Add targeted fallback translations for low-coverage countries such as Morocco, UAE, and Vietnam
