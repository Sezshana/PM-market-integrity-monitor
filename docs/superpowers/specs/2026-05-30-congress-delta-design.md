# Congressional Bill Tracker — Delta-Only Design

**Date:** 2026-05-30  
**Status:** Approved  
**Repo:** polymarket-osint-monitor (PM-market-integrity-monitor)

## Problem

The daily digest includes a **Congressional Bill Tracker** section that lists all seven watched bills every day with the same `latest_action` and dates (often weeks stale). This adds noise without signal. The user wants the section to **synthesize updates and changes** and flag them when relevant — not repeat a static status table.

## Goals

1. Show per-bill detail **only when** status changes or a bill is newly added to the watchlist.
2. On quiet days, show a **single line**: no movement since last change, with monitored count.
3. Surface bill movement in the **narrative summary** and subject line when it is material.
4. First run after deploy **seeds state silently** (no flood of “7 new bills”).
5. Follow the existing **OFAC pattern** (delta-only sections).

## Non-Goals (this iteration)

- Weekly congressional rollup email section.
- Congress.gov keyword search for auto-discovering new bills (Phase 3 backlog).
- Fetching full `/actions` history per bill (higher API cost; defer unless `latestAction` proves insufficient).

## Current Behavior

- `check_congress_bills()` in `src/polymarket_monitor/clients/congress.py` fetches each bill’s `latestAction` from Congress.gov v3 API.
- Returns all bills every run; `monitor.py` and `email_template.py` render the full list.
- Duplicate legacy `check_congress_bills()` still exists in `monitor.py` but `main()` uses the client import.

## Proposed Behavior

### State file

Path: `data/congress_bill_state.json`

```json
{
  "bills": {
    "HR8076": {
      "bill": "PREDICT Act",
      "latest_action": "Referred to the Committee on...",
      "action_date": "2026-03-25",
      "url": "https://www.congress.gov/bill/...",
      "last_changed": "2026-03-25",
      "last_checked": "2026-05-30"
    }
  },
  "meta": {
    "seeded_at": "2026-05-30",
    "last_movement_date": "2026-03-26"
  }
}
```

- Keyed by normalized bill id (`HR8076`, `S4017`, …).
- Updated after each successful fetch pass.
- Committed to repo like `seen_articles.json` and `story_threads.json`.

### Change detection

For each bill in `config.BILLS`:

| Condition | `change_type` | Digest treatment |
|-----------|---------------|------------------|
| Bill id not in state | `new_watchlist` | Full card; flag as newly tracked |
| `latest_action` or `action_date` differs from state | `status_change` | Card with before → after |
| No difference | — | Omitted from detail list |

**First run (empty state):** populate state from API results; return **zero** changes to the report (seed only, no email noise).

### Report contract

Replace ambiguous `bill_updates` payload with structured output:

```python
{
  "changes": [  # only items with movement or new watchlist
    {
      "bill": "STOP Corrupt Bets Act",
      "id": "S4226",
      "change_type": "status_change",  # or "new_watchlist"
      "previous_action": "Read twice and referred to...",
      "previous_date": "2026-03-20",
      "latest_action": "Placed on Senate Legislative Calendar...",
      "action_date": "2026-05-28",
      "url": "https://www.congress.gov/..."
    }
  ],
  "quiet_message": "No congressional bill movement since 2026-03-26. (7 bills monitored.)",
  "monitored_count": 7,
  "movement_count": 0
}
```

- `build_daily_report()` / JSON schema: add `bill_tracker` object; keep `bill_updates` as deprecated alias mapping to `changes` for one release, or migrate in same PR.
- Source status detail: `"0 bill movements; 7 monitored"` not `"7 bill updates"`.

### Email (plain + HTML)

**When `movement_count > 0`:**

- Section title: **Congressional Updates** (not “Tracker”).
- Each row: bill name, change type badge, previous → latest action, date, link.

**When `movement_count == 0`:**

- One line only (user preference):  
  `No congressional bill movement since {last_movement_date}. (7 bills monitored.)`
- No per-bill rows, no stat box implying activity.

### Narrative and subject

- `build_narrative_summary()`: if `movement_count > 0`, append sentence listing bills that moved (max 2 names + “and N more”).
- `build_subject()`: optional prefix when bill movement is the only notable signal on a quiet market day.

### Quiet day mode

- `is_quiet` unchanged for markets/news; congress one-liner still appears (confirms monitoring active).
- Do not append “Congressional bill status and general news below” when bills are one-liner only — reword to avoid promising a full tracker section.

### Watchlist changes

- Adding a bill to `BILLS` in `config.py` triggers `new_watchlist` on first sight after seed exists.
- Removing a bill: drop from state on next run; no email unless we add explicit “removed from watchlist” (out of scope).

## Architecture

```
config.BILLS
    → congress.fetch_and_diff_bills()
        → load state (data/congress_bill_state.json)
        → API fetch per bill
        → diff → BillTrackerResult
        → save state
    → monitor.build_email / email_template / build_daily_report
```

New module recommended: `src/polymarket_monitor/detectors/congress_tracker.py` (diff + state I/O) with thin client remaining in `clients/congress.py` for HTTP only.

## Error handling

- API failure for one bill: log, keep prior state for that id, do not falsely report change.
- All bills fail: `mark_source("Congress", STATUS_FAILED)`; quiet message notes check failed.
- Missing `CONGRESS_API_KEY`: skip section; existing skip behavior.

## Testing

- Unit tests with mocked API responses and fixture state file:
  - seed run returns zero changes
  - status text change detected
  - action_date-only change detected
  - new watchlist bill detected
  - quiet message uses `last_movement_date` from meta
- Report contract test updated for `bill_tracker` shape.

## Files to modify

| File | Change |
|------|--------|
| `src/polymarket_monitor/clients/congress.py` | HTTP fetch only, or delegate to tracker |
| `src/polymarket_monitor/detectors/congress_tracker.py` | **Create** — diff, state, result type |
| `src/polymarket_monitor/config.py` | `BILL_STATE_FILE` path constant |
| `src/polymarket_monitor/reporting/schema.py` | `bill_tracker` field |
| `monitor.py` | Remove duplicate congress fn; wire tracker; narrative/subject |
| `email_template.py` | Changes vs one-liner rendering |
| `tests/test_congress_tracker.py` | **Create** |
| `tests/test_report_contract.py` | Schema expectations |
| `data/congress_bill_state.json` | **Create** on first CI run (or seed in workflow) |

## Success criteria

- [ ] Two consecutive quiet days produce **identical one-liner**, not seven bill blocks.
- [ ] Simulated `latest_action` change appears in email, narrative, and JSON `changes`.
- [ ] New bill in `BILLS` after seed flags `new_watchlist` once.
- [ ] First deploy does not send seven “new bill” cards.

## Follow-on (Phase 1 backlog, separate plans)

- Apply same delta-only pattern audit to other repetitive sections.
- Congress.gov search suggestions for new PM legislation.
- Extract report builder from monolithic `monitor.py`.
