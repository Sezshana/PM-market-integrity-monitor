# Architecture

## Current Shape

The monitor is still a prototype-style repository with top-level scripts:

```text
monitor.py              collection, detection, scoring, reporting, email
wash_trading_module.py  coordinated-trading review signals
aggregator.py           cross-day state and dashboard aggregates
email_template.py       HTML digest rendering
dashboard.html          static dashboard over generated JSON
```

This is acceptable for the current stage, but new work should avoid making
`monitor.py` more responsible than it already is.

## Target Boundaries

When the repo is ready for a larger refactor, split responsibilities toward:

```text
clients/      external APIs and RSS feeds
detectors/    heuristic signal logic and thresholds
reporting/    Markdown, HTML email, and dashboard exports
storage/      JSON/SQLite state and retention
learning/     analyst corrections and detector review history
```

Do not start this restructure in a guardrails-only PR.

## Data Flow

```text
External sources
  -> source fetchers in monitor.py / onchain helpers
  -> detector and scoring logic
  -> output/report_<date>.json
  -> aggregator.py
  -> data/aggregate_intelligence.json
  -> dashboard.html and email digest
```

## Data Sensitivity

The repo can run in two modes:

- **Public demo/dashboard mode**: generated `output/` and `data/` files are
  intentionally versioned and must be sanitized.
- **Private operational mode**: generated reports, case notes, state files, and
  watchlists should not be committed.

Every PR that changes generated data handling must state which mode it supports.

## Reporting Standard

Generated copy should describe observed criteria:

- "Criteria matched"
- "Flagged by heuristic"
- "Shared funder observed"
- "Repeated counterparty pattern observed"
- "Near-zero net exposure observed"
- "Analyst review required"

Avoid unsupported conclusions about intent, identity, ownership, insider access,
or wrongdoing.

## Testing Strategy

Start with offline unit tests for:

- Watchlist parsing
- RSS/article deduplication
- Priority scoring
- Market filtering
- Low-probability/high-volume review criteria
- Repeated counterparty detection
- Near-zero net exposure detection
- Report JSON schema

Network-backed checks should be integration tests with explicit opt-in because
the public APIs can rate-limit or change shape.
