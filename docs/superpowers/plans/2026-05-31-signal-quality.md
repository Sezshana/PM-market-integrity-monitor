# Signal Quality Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve daily digest signal quality with layered news, tiered markets, regulatory snapshot, and cross-source ranking so quiet RSS days still read as useful intelligence.

**Architecture:** New detector modules build structured layers (`NewsLayers`, `MarketTierResult`, `RegulatorySnapshot`, `DigestRankResult`); `monitor.py` orchestrates and delegates rendering to `reporting/digest_sections.py` and `email_template.py`. Report JSON gains optional fields while keeping backward-compatible keys.

**Tech Stack:** Python 3.11, unittest, existing RSS/Polymarket/Congress/OFAC/UMA clients, JSON state files.

**Spec:** `docs/superpowers/specs/2026-05-31-signal-quality-design.md`

---

### Task 1: News layers module

**Files:**
- Create: `src/polymarket_monitor/detectors/news_layers.py`
- Modify: `src/polymarket_monitor/config.py`
- Test: `tests/test_news_layers.py`

- [ ] **Step 1: Add config constants**

In `src/polymarket_monitor/config.py`:

```python
ONGOING_WATCH_MAX_DAYS = 7
ONGOING_WATCH_MAX_ITEMS = 3
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_news_layers.py`:

```python
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from polymarket_monitor.detectors.news_layers import (  # noqa: E402
    NewsLayers,
    build_news_layers,
)


class NewsLayersTests(unittest.TestCase):
    def test_ongoing_watch_includes_threads_within_seven_days(self):
        today = date.today()
        recent = (today - timedelta(days=2)).isoformat()
        old = (today - timedelta(days=10)).isoformat()
        threads = {
            "active": {
                "representative_title": "Congress probe into Polymarket",
                "dates_seen": ["2026-05-01", recent],
                "last_seen": recent,
                "mention_count": 2,
            },
            "stale": {
                "representative_title": "Old story",
                "dates_seen": ["2026-05-01", old],
                "last_seen": old,
                "mention_count": 2,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "story_threads.json"
            path.write_text(json.dumps(threads))
            layers = build_news_layers(
                new_today=[],
                story_threads_path=path,
                max_days=7,
                max_items=3,
            )
        self.assertEqual(len(layers.ongoing_watch), 1)
        self.assertEqual(layers.ongoing_watch[0]["representative_title"], "Congress probe into Polymarket")

    def test_ongoing_watch_caps_at_max_items(self):
        today = date.today().isoformat()
        threads = {
            f"t{i}": {
                "representative_title": f"Story {i}",
                "dates_seen": ["2026-05-01", today],
                "last_seen": today,
                "mention_count": 2 + i,
            }
            for i in range(5)
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "story_threads.json"
            path.write_text(json.dumps(threads))
            layers = build_news_layers([], path, max_days=7, max_items=3)
        self.assertEqual(len(layers.ongoing_watch), 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/shanabautista/Documents/GitHub/polymarket-osint-monitor && PYTHONPATH=src python3 -m unittest tests.test_news_layers -v`  
Expected: FAIL — `ModuleNotFoundError` or missing `build_news_layers`

- [ ] **Step 4: Implement news_layers.py**

```python
# src/polymarket_monitor/detectors/news_layers.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any


@dataclass
class NewsLayers:
    new_today: list[dict[str, Any]] = field(default_factory=list)
    ongoing_watch: list[dict[str, Any]] = field(default_factory=list)


def _load_threads(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def build_ongoing_watch(
    threads: dict[str, Any],
    *,
    max_days: int = 7,
    max_items: int = 3,
    today: date | None = None,
) -> list[dict[str, Any]]:
    today = today or date.today()
    cutoff = (today - timedelta(days=max_days)).isoformat()
    ongoing = [
        thread
        for thread in threads.values()
        if thread.get("mention_count", 0) >= 2 and thread.get("last_seen", "") >= cutoff
    ]
    ongoing.sort(
        key=lambda t: (t.get("mention_count", 0), t.get("last_seen", "")),
        reverse=True,
    )
    return ongoing[:max_items]


def build_news_layers(
    new_today: list[dict[str, Any]],
    story_threads_path: Path,
    *,
    max_days: int = 7,
    max_items: int = 3,
) -> NewsLayers:
    threads = _load_threads(story_threads_path)
    return NewsLayers(
        new_today=new_today,
        ongoing_watch=build_ongoing_watch(threads, max_days=max_days, max_items=max_items),
    )
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=src python3 -m unittest tests.test_news_layers -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/polymarket_monitor/config.py src/polymarket_monitor/detectors/news_layers.py tests/test_news_layers.py
git commit -m "Add news layers for ongoing watch threads."
```

---

### Task 2: Market tiering module

**Files:**
- Create: `src/polymarket_monitor/detectors/market_tiering.py`
- Modify: `src/polymarket_monitor/config.py`
- Test: `tests/test_market_tiering.py`

- [ ] **Step 1: Add LOW_BODY_VOLUME_USD to config**

```python
LOW_BODY_VOLUME_USD = 2_000_000
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_market_tiering.py — key test
def test_low_volume_sports_stays_secondary_only(self):
    markets = [{
        "question": "Will Team A win Game 2?",
        "insider_risk": "LOW",
        "volume_usd": 500_000,
        "days_until_close": 1,
        "wash_score": 0,
        "watchlist_hit": [],
    }]
    result = tier_markets(markets)
    self.assertEqual(len(result.primary), 0)
    self.assertEqual(result.secondary_count, 1)
```

- [ ] **Step 3: Implement tier_markets**

```python
@dataclass
class MarketTierResult:
    primary: list[dict[str, Any]]
    secondary: list[dict[str, Any]]
    secondary_count: int


def tier_markets(
    markets: list[dict[str, Any]],
    *,
    low_body_volume_usd: float = 2_000_000,
    wash_reports_by_market: dict[str, Any] | None = None,
) -> MarketTierResult:
    primary, secondary = [], []
    for m in markets:
        risk = m.get("insider_risk", "MEDIUM")
        if risk in ("HIGH", "MEDIUM"):
            primary.append(m)
            continue
        promoted = (
            bool(m.get("watchlist_hit"))
            or float(m.get("volume_usd", 0) or 0) >= low_body_volume_usd
            or (wash_reports_by_market or {}).get(m.get("market_id"), {}).get("wash_score", 0) >= 4
        )
        (primary if promoted else secondary).append(m)
    return MarketTierResult(primary=primary, secondary=secondary, secondary_count=len(secondary))
```

- [ ] **Step 4: Run tests and commit**

```bash
git add src/polymarket_monitor/detectors/market_tiering.py src/polymarket_monitor/config.py tests/test_market_tiering.py
git commit -m "Add market tiering to separate primary and secondary flags."
```

---

### Task 3: Regulatory snapshot module

**Files:**
- Create: `src/polymarket_monitor/detectors/regulatory_snapshot.py`
- Test: `tests/test_regulatory_snapshot.py`

- [ ] **Step 1: Write failing test for synthesis string**

```python
def test_all_quiet_synthesis(self):
    snap = build_regulatory_snapshot(
        bill_tracker=BillTrackerResult(quiet_message="No movement since 2026-03-26.", monitored_count=7),
        ofac=[],
        uma=[],
    )
    self.assertIn("no bill movement", snap.synthesis.lower())
    self.assertIn("no new ofac", snap.synthesis.lower())
```

- [ ] **Step 2: Implement build_regulatory_snapshot**

Return `RegulatorySnapshot` with `.synthesis` one-liner and `.lines` list for email rows.

- [ ] **Step 3: Run tests and commit**

```bash
git commit -m "Add regulatory snapshot synthesis for digest."
```

---

### Task 4: Digest ranker

**Files:**
- Create: `src/polymarket_monitor/detectors/digest_ranker.py`
- Test: `tests/test_digest_ranker.py`

- [ ] **Step 1: Write failing test — market beats empty news**

```python
def test_high_market_leads_when_no_news(self):
    result = rank_digest(
        news_layers=NewsLayers(new_today=[], ongoing_watch=[]),
        market_tiers=MarketTierResult(primary=[{"question": "Q", "insider_risk": "HIGH", "volume_usd": 1e6, "probability_pct": 2, "days_until_close": 10}], secondary=[], secondary_count=0),
        regulatory_snapshot=...,
    )
    self.assertIn("Q", result.narrative_lead)
    self.assertNotIn("No new news articles today", result.narrative_lead)
```

- [ ] **Step 2: Implement rank_digest + build_subject_from_rank**

- [ ] **Step 3: Run tests and commit**

```bash
git commit -m "Add cross-source digest ranker for narrative and subject."
```

---

### Task 5: Wire monitor + narrative

**Files:**
- Modify: `monitor.py`
- Modify: `src/polymarket_monitor/reporting/schema.py`
- Modify: `tests/test_report_contract.py`

- [ ] **Step 1: Update main() flow**

After RSS fetch:

```python
news_layers = build_news_layers(news, config.STORY_THREADS, max_days=config.ONGOING_WATCH_MAX_DAYS, max_items=config.ONGOING_WATCH_MAX_ITEMS)
market_tiers = tier_markets(suspicious_markets, wash_reports_by_market=wash_by_market)
reg_snapshot = build_regulatory_snapshot(bill_tracker, ofac, uma)
rank = rank_digest(news_layers, market_tiers, reg_snapshot, large_trades, source_coverage=get_source_status())
narrative = rank.narrative_lead  # or build_narrative_from_rank(rank, ...)
subject = build_subject_from_rank(rank, is_quiet=...)
```

- [ ] **Step 2: Extend DailyReport / build_daily_report**

Add optional fields: `news_layers`, `markets_primary`, `markets_secondary_count`, `regulatory_snapshot`, `digest_rank` (dicts via `.to_dict()`).

Keep `suspicious_market_data` = primary markets for dashboard compat.

- [ ] **Step 3: Update contract tests**

- [ ] **Step 4: Run full unittest suite**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`

- [ ] **Step 5: Commit**

```bash
git commit -m "Wire signal quality layers into monitor orchestration."
```

---

### Task 6: Email and plain-text sections

**Files:**
- Create: `src/polymarket_monitor/reporting/digest_sections.py`
- Modify: `email_template.py`
- Modify: `monitor.py` (`build_email` delegates or inlines section calls)
- Modify: `dashboard.html` (ongoing watch + secondary count if time)

- [ ] **Step 1: Implement plain section builders**

Functions: `render_ongoing_watch`, `render_regulatory_snapshot`, `render_source_health`, `render_secondary_markets_footer`.

- [ ] **Step 2: Reorder email_template sections per spec section 5**

Pass `NewsLayers`, `MarketTierResult`, `RegulatorySnapshot` into `build_html_email`.

- [ ] **Step 3: Manual smoke**

Run: `PYTHONPATH=src python3 monitor.py` with secrets locally OR inspect generated `output/report_*.md` in CI artifact.

- [ ] **Step 4: Update README** — document layered news and market tiers.

- [ ] **Step 5: Commit and push**

```bash
git commit -m "Update email and report layout for signal quality layers."
git push
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Ongoing watch 7d / max 3 | Task 1 |
| Narrative when news empty | Task 4, 5 |
| Market tiering LOW collapsed | Task 2, 6 |
| Regulatory snapshot | Task 3, 6 |
| Cross-source subject | Task 4, 5 |
| Source health line | Task 6 |
| Schema fields | Task 5 |
| Tests | All tasks |

---

## Execution choice

Plan complete and saved to `docs/superpowers/plans/2026-05-31-signal-quality.md`.

1. **Subagent-driven** — one task per subagent with review between tasks  
2. **Inline** — implement in this session with checkpoints after Tasks 2 and 5

Which approach do you want?
