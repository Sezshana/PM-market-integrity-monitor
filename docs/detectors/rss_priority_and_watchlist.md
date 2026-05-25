# Signal Card: RSS Priority and Watchlist Review

## Signal Name

RSS priority and watchlist review

Status: active

## Purpose

Collect relevant regulatory, market-structure, and Polymarket-related news,
deduplicate similar articles, and prioritize items for the daily digest.

## Data Sources

- Sources: configured RSS feeds in `RSS_FEEDS`
- Collection method: `feedparser.parse`
- Required credentials: none
- Expected refresh cadence: daily workflow
- Known source limitations: feed availability, incomplete summaries, and
  publisher timestamp differences.

## Detection Criteria

```text
Article title or summary matches at least one keyword in KEYWORDS.
Noise terms are excluded unless a strong Polymarket-specific signal is present.
Watchlist keyword/wallet matches elevate priority.
Priority score is calculated from PRIORITY_WEIGHTS.
Similar titles are clustered by title fingerprint.
The highest-priority source in each cluster is retained.
Previously seen URLs are skipped unless DEMO_MODE is true.
```

## Thresholds

```text
priority = score >= 3 or watchlist hit present
seen article cache retains last 500 URLs
developing story window retains threads seen in the last 14 days
```

## Output Fields

```text
source: RSS source name
title: Article title
link: Article URL
published: Raw published timestamp
pub_date: Parsed display date
matched_keywords: Matching keywords
summary: Cleaned summary
score: Priority score
priority: Boolean priority flag
watchlist_hit: Watchlist matches
also_covered_by: Other sources in deduplication cluster
```

## Known False Positives

- Generic crypto regulation articles that mention prediction markets only in
  passing.
- Articles with sensational terms but little operational relevance.
- Duplicate headlines with enough wording variation to evade clustering.

## Alternative Explanations

- Publisher syndication
- Keyword collision with unrelated market topics
- Repeated coverage of an already-reviewed story

## Analyst Review Actions

1. Read high-priority articles first.
2. Check whether watchlist hits are contextual or incidental.
3. Review `also_covered_by` for broad coverage vs duplicate syndication.
4. Use developing story threads to avoid overreacting to repeated coverage.

## Tests

- Existing unit tests cover watchlist parsing, priority scoring, and source
  priority deduplication.
- Additional tests should cover noise exclusions and seen-URL filtering.

## Reporting Language

Preferred:

```text
High priority news alert based on keyword/watchlist criteria.
```

Avoid:

```text
The article confirms misconduct.
```
