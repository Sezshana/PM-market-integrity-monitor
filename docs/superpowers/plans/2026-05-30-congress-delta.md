# Congressional Bill Delta Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show congressional bill detail in the daily digest only when status changes or a bill is newly added; otherwise one quiet line per day.

**Architecture:** Congress.gov client fetches bill JSON; `congress_tracker` diffs against `data/congress_bill_state.json` and returns a structured `BillTrackerResult`; report/email/narrative consume that result. First run seeds state with zero surfaced changes.

**Tech Stack:** Python 3.11, requests, Congress.gov v3 API, existing unittest suite, JSON state files.

**Spec:** `docs/superpowers/specs/2026-05-30-congress-delta-design.md`

---

### Task 1: Bill tracker core (state + diff)

**Files:**
- Create: `src/polymarket_monitor/detectors/congress_tracker.py`
- Modify: `src/polymarket_monitor/config.py`
- Test: `tests/test_congress_tracker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_congress_tracker.py
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from polymarket_monitor.detectors.congress_tracker import (
    BillTrackerResult,
    diff_bills_against_state,
    load_bill_state,
    save_bill_state,
)


class CongressTrackerTests(unittest.TestCase):
    def test_seed_run_returns_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "congress_bill_state.json"
            fetched = [
                {
                    "id": "S4226",
                    "bill": "STOP Corrupt Bets Act",
                    "latest_action": "Referred to Ag",
                    "action_date": "2026-03-26",
                    "url": "https://example.com/s4226",
                }
            ]
            result = diff_bills_against_state(fetched, state_path, monitored_count=1)
            self.assertEqual(result.movement_count, 0)
            self.assertEqual(result.changes, [])
            saved = json.loads(state_path.read_text())
            self.assertIn("S4226", saved["bills"])

    def test_status_change_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "congress_bill_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "bills": {
                            "S4226": {
                                "bill": "STOP Corrupt Bets Act",
                                "latest_action": "Old action",
                                "action_date": "2026-03-20",
                                "url": "https://example.com/s4226",
                                "last_changed": "2026-03-20",
                                "last_checked": "2026-05-29",
                            }
                        },
                        "meta": {"last_movement_date": "2026-03-20"},
                    }
                )
            )
            fetched = [
                {
                    "id": "S4226",
                    "bill": "STOP Corrupt Bets Act",
                    "latest_action": "New action",
                    "action_date": "2026-05-28",
                    "url": "https://example.com/s4226",
                }
            ]
            result = diff_bills_against_state(fetched, state_path, monitored_count=1)
            self.assertEqual(result.movement_count, 1)
            self.assertEqual(result.changes[0]["change_type"], "status_change")
            self.assertEqual(result.changes[0]["previous_action"], "Old action")
            self.assertEqual(result.changes[0]["latest_action"], "New action")

    def test_quiet_message_uses_last_movement_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "congress_bill_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "bills": {
                            "S4226": {
                                "bill": "STOP",
                                "latest_action": "Same",
                                "action_date": "2026-03-26",
                                "url": "https://example.com",
                                "last_changed": "2026-03-26",
                                "last_checked": "2026-05-29",
                            }
                        },
                        "meta": {"last_movement_date": "2026-03-26"},
                    }
                )
            )
            fetched = [
                {
                    "id": "S4226",
                    "bill": "STOP",
                    "latest_action": "Same",
                    "action_date": "2026-03-26",
                    "url": "https://example.com",
                }
            ]
            result = diff_bills_against_state(fetched, state_path, monitored_count=7)
            self.assertIn("2026-03-26", result.quiet_message)
            self.assertIn("7 bills monitored", result.quiet_message)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shanabautista/Documents/GitHub/polymarket-osint-monitor && PYTHONPATH=src python3 -m unittest tests.test_congress_tracker -v`  
Expected: FAIL — `ModuleNotFoundError` or missing `diff_bills_against_state`

- [ ] **Step 3: Implement tracker module**

```python
# src/polymarket_monitor/detectors/congress_tracker.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass
class BillTrackerResult:
    changes: list[dict[str, Any]] = field(default_factory=list)
    quiet_message: str = ""
    monitored_count: int = 0
    movement_count: int = 0


def load_bill_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"bills": {}, "meta": {}}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"bills": {}, "meta": {}}


def save_bill_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def diff_bills_against_state(
    fetched: list[dict[str, Any]],
    state_path: Path,
    monitored_count: int,
) -> BillTrackerResult:
    state = load_bill_state(state_path)
    bills_state: dict[str, Any] = state.setdefault("bills", {})
    meta: dict[str, Any] = state.setdefault("meta", {})
    is_seed = len(bills_state) == 0
    changes: list[dict[str, Any]] = []
    today = date.today().isoformat()

    for row in fetched:
        bill_id = row["id"].upper()
        prev = bills_state.get(bill_id)
        if prev is None and not is_seed:
            changes.append(
                {
                    **row,
                    "change_type": "new_watchlist",
                    "previous_action": None,
                    "previous_date": None,
                }
            )
        elif prev is not None and (
            prev.get("latest_action") != row.get("latest_action")
            or prev.get("action_date") != row.get("action_date")
        ):
            changes.append(
                {
                    **row,
                    "change_type": "status_change",
                    "previous_action": prev.get("latest_action"),
                    "previous_date": prev.get("action_date"),
                }
            )
        elif prev is not None and not is_seed:
            pass  # no movement
        # update state for every successfully fetched row
        last_changed = today if (
            prev is None
            or prev.get("latest_action") != row.get("latest_action")
            or prev.get("action_date") != row.get("action_date")
        ) else prev.get("last_changed", today)
        if is_seed:
            last_changed = row.get("action_date") or today
        bills_state[bill_id] = {
            "bill": row.get("bill"),
            "latest_action": row.get("latest_action"),
            "action_date": row.get("action_date"),
            "url": row.get("url"),
            "last_changed": last_changed,
            "last_checked": today,
        }

    if changes:
        meta["last_movement_date"] = today
    elif not meta.get("last_movement_date"):
        dates = [b.get("last_changed") for b in bills_state.values() if b.get("last_changed")]
        meta["last_movement_date"] = max(dates) if dates else today
    if is_seed:
        meta.setdefault("seeded_at", today)
        changes = []

    save_bill_state(state_path, state)
    last_mv = meta.get("last_movement_date", today)
    quiet = (
        f"No congressional bill movement since {last_mv}. "
        f"({monitored_count} bills monitored.)"
    )
    return BillTrackerResult(
        changes=changes,
        quiet_message=quiet,
        monitored_count=monitored_count,
        movement_count=len(changes),
    )
```

Add to `config.py`:

```python
BILL_STATE_FILE = Path("data/congress_bill_state.json")
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=src python3 -m unittest tests.test_congress_tracker -v`  
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/polymarket_monitor/detectors/congress_tracker.py src/polymarket_monitor/config.py tests/test_congress_tracker.py
git commit -m "Add congressional bill state diff tracker."
```

---

### Task 2: Wire Congress client to tracker

**Files:**
- Modify: `src/polymarket_monitor/clients/congress.py`
- Modify: `monitor.py`

- [ ] **Step 1: Refactor client to return fetched rows + tracker result**

In `clients/congress.py`, add:

```python
from polymarket_monitor.config import BILL_STATE_FILE, BILLS
from polymarket_monitor.detectors.congress_tracker import BillTrackerResult, diff_bills_against_state

def fetch_bill_snapshots(bills: list[dict[str, str]]) -> list[dict[str, Any]]:
    # existing per-bill HTTP loop; return list of row dicts (no diff)

def check_congress_bills(bills: list[dict[str, str]] | None = None) -> BillTrackerResult:
    bills = bills or BILLS
    rows = fetch_bill_snapshots(bills)
    result = diff_bills_against_state(rows, BILL_STATE_FILE, monitored_count=len(bills))
    detail = f"{result.movement_count} bill movements; {result.monitored_count} monitored"
    mark_source("Congress", STATUS_OK if rows else STATUS_FAILED, detail=detail, records=result.movement_count)
    return result
```

- [ ] **Step 2: Update monitor.py**

- Delete duplicate `check_congress_bills` function (lines ~748–769).
- In `main()`: `bill_tracker = check_congress_bills(BILLS)`.
- Pass `bill_tracker` through `save_report` / `build_email` instead of raw list.

- [ ] **Step 3: Run existing tests**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`  
Expected: congress tests PASS; fix any contract failures in Task 3.

- [ ] **Step 4: Commit**

```bash
git add src/polymarket_monitor/clients/congress.py monitor.py
git commit -m "Wire congress client to delta tracker."
```

---

### Task 3: Report schema and contract tests

**Files:**
- Modify: `src/polymarket_monitor/reporting/schema.py`
- Modify: `tests/test_report_contract.py`
- Modify: `tests/test_schema_and_review_store.py`

- [ ] **Step 1: Add `bill_tracker` to daily report schema**

```python
# In build_daily_report kwargs / DailyReport dataclass
bill_tracker: dict[str, Any]  # serialized BillTrackerResult

# bill_updates = bill_tracker["changes"]  # backward compat for dashboard one release
```

- [ ] **Step 2: Update contract test required keys**

Add `"bill_tracker"` to `REQUIRED_REPORT_KEYS`; allow `bill_updates` to mirror `changes` for compatibility.

- [ ] **Step 3: Run contract tests**

Run: `PYTHONPATH=src python3 -m unittest tests.test_report_contract tests.test_schema_and_review_store -v`

- [ ] **Step 4: Commit**

```bash
git add src/polymarket_monitor/reporting/schema.py tests/test_report_contract.py tests/test_schema_and_review_store.py
git commit -m "Add bill_tracker field to daily report schema."
```

---

### Task 4: Email and plain-text report rendering

**Files:**
- Modify: `monitor.py` (`build_email`, `build_plain_report` section ~1094)
- Modify: `email_template.py`

- [ ] **Step 1: Plain text — changes vs one-liner**

Replace `CONGRESSIONAL BILL TRACKER` block with:

```python
if bill_tracker.movement_count:
    lines += ["CONGRESSIONAL UPDATES", "=" * 60]
    for c in bill_tracker.changes:
        lines += [
            f"\n{c['bill']} ({c['id']}) — {c['change_type'].replace('_', ' ').title()}",
            f"   Was:    {c.get('previous_action') or 'n/a'} ({c.get('previous_date') or 'n/a'})",
            f"   Now:    {c['latest_action']}",
            f"   Date:   {c.get('action_date', 'N/A')}",
            f"   Link:   {c['url']}",
        ]
else:
    lines += [bill_tracker.quiet_message]
lines.append("")
```

- [ ] **Step 2: HTML template**

- Stat box: `Bill movements today` = `movement_count` (not len(bills)).
- Section: if `movement_count > 0`, render change rows with before/after; else single muted `<p>` with `quiet_message`.

- [ ] **Step 3: At-a-glance line**

Change `Bills tracked: {len(bills)}` → `Bill movements today: {bill_tracker.movement_count}`.

- [ ] **Step 4: Quiet day copy**

Remove “Congressional bill status and general news below” when only one-liner congress.

- [ ] **Step 5: Commit**

```bash
git add monitor.py email_template.py
git commit -m "Render congress section as delta updates or one-liner."
```

---

### Task 5: Narrative and subject line

**Files:**
- Modify: `monitor.py` (`build_narrative_summary`, `build_subject`)

- [ ] **Step 1: Narrative mentions bill movement**

```python
def build_narrative_summary(..., bill_tracker: BillTrackerResult | None = None):
    ...
    if bill_tracker and bill_tracker.movement_count:
        names = [c["bill"] for c in bill_tracker.changes[:2]]
        suffix = ""
        if bill_tracker.movement_count > 2:
            suffix = f" and {bill_tracker.movement_count - 2} more"
        parts.append(
            f"{bill_tracker.movement_count} congressional bill(s) moved: {', '.join(names)}{suffix}."
        )
```

- [ ] **Step 2: Subject when bills are only signal**

If `is_quiet` and `bill_tracker.movement_count`, prefix subject with bill name.

- [ ] **Step 3: Manual smoke**

Run locally with `CONGRESS_API_KEY` set (or mock): `PYTHONPATH=src python3 -c "from polymarket_monitor.clients.congress import check_congress_bills; print(check_congress_bills())"`

- [ ] **Step 4: Commit**

```bash
git add monitor.py
git commit -m "Surface congressional bill movement in narrative and subject."
```

---

### Task 6: Seed state in CI and document

**Files:**
- Modify: `README.md` (Congress section description)
- Optional: `data/congress_bill_state.json` seeded from current API in workflow first run

- [ ] **Step 1: Update README**

Document delta-only behavior and `data/congress_bill_state.json`.

- [ ] **Step 2: Run full test suite**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`  
Expected: all pass except any pre-existing unrelated failures (note in PR).

- [ ] **Step 3: Commit and push**

```bash
git add README.md data/congress_bill_state.json docs/
git commit -m "Document congressional delta tracker; seed bill state."
git push
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| State file `congress_bill_state.json` | Task 1 |
| Seed run, zero changes | Task 1 tests |
| status_change / new_watchlist | Task 1 |
| Quiet one-liner | Task 1, 4 |
| Report `bill_tracker` contract | Task 3 |
| Email changes vs one-liner | Task 4 |
| Narrative + subject | Task 5 |
| Remove duplicate monitor fn | Task 2 |
| Source status wording | Task 2 |

## Execution choice

After this plan is committed, choose:

1. **Subagent-driven** — one task per subagent with review between tasks  
2. **Inline** — implement all tasks in this session with checkpoints
