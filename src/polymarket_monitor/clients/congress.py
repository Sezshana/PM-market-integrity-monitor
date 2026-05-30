"""Congress.gov bill tracking client."""

from __future__ import annotations

from typing import Any

import requests

from polymarket_monitor import config
from polymarket_monitor.detectors.congress_tracker import BillTrackerResult, diff_bills_against_state
from polymarket_monitor.source_status import STATUS_FAILED, STATUS_OK, STATUS_SKIPPED, mark_source


def fetch_bill_snapshots(bills: list[dict[str, str]]) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    failures = 0
    for bill in bills:
        try:
            bt = "hr" if bill["id"].startswith("hr") else "s"
            bn = bill["id"].replace("hr", "").replace("s", "")
            url = f"https://api.congress.gov/v3/bill/{bill['congress']}/{bt}/{bn}"
            resp = requests.get(url, params={"api_key": config.CONGRESS_KEY}, timeout=10)
            if resp.status_code == 200:
                bd = resp.json().get("bill", {})
                rows.append({
                    "bill": bill["name"],
                    "id": bill["id"].upper(),
                    "latest_action": bd.get("latestAction", {}).get("text", "No action found"),
                    "action_date": bd.get("latestAction", {}).get("actionDate", ""),
                    "url": (
                        f"https://www.congress.gov/bill/{bill['congress']}th-congress/"
                        f"{'house' if bt == 'hr' else 'senate'}-bill/{bn}"
                    ),
                })
            else:
                failures += 1
                print(f"  Bill error [{bill['name']}]: HTTP {resp.status_code}")
        except Exception as e:
            failures += 1
            print(f"  Bill error [{bill['name']}]: {e}")
    return rows, failures


def check_congress_bills(bills: list[dict[str, str]] | None = None) -> BillTrackerResult:
    bills = bills or config.BILLS
    if not config.CONGRESS_KEY:
        mark_source("Congress", STATUS_SKIPPED, detail="CONGRESS_API_KEY not configured", records=0)
        return BillTrackerResult(monitored_count=len(bills))

    rows, failures = fetch_bill_snapshots(bills)
    result = diff_bills_against_state(rows, config.BILL_STATE_FILE, monitored_count=len(bills))

    if failures == len(bills) and bills:
        mark_source("Congress", STATUS_FAILED, detail="All bill fetches failed", records=0)
    else:
        detail = f"{result.movement_count} bill movements; {result.monitored_count} monitored"
        if failures:
            detail += f"; {failures} fetch failures"
        mark_source("Congress", STATUS_OK, detail=detail, records=result.movement_count)
    return result
