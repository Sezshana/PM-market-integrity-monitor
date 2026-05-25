"""Congress.gov bill tracking client."""

from __future__ import annotations

from typing import Any

import requests

from polymarket_monitor import config
from polymarket_monitor.source_status import STATUS_FAILED, STATUS_OK, STATUS_SKIPPED, mark_source


def check_congress_bills(bills: list[dict[str, str]]) -> list[dict[str, Any]]:
    updates = []
    if not config.CONGRESS_KEY:
        mark_source("Congress", STATUS_SKIPPED, detail="CONGRESS_API_KEY not configured", records=0)
        return updates
    failures = 0
    for bill in bills:
        try:
            bt = "hr" if bill["id"].startswith("hr") else "s"
            bn = bill["id"].replace("hr", "").replace("s", "")
            url = f"https://api.congress.gov/v3/bill/{bill['congress']}/{bt}/{bn}"
            resp = requests.get(url, params={"api_key": config.CONGRESS_KEY}, timeout=10)
            if resp.status_code == 200:
                bd = resp.json().get("bill", {})
                updates.append({
                    "bill": bill["name"],
                    "id": bill["id"].upper(),
                    "latest_action": bd.get("latestAction", {}).get("text", "No action found"),
                    "action_date": bd.get("latestAction", {}).get("actionDate", ""),
                    "url": f"https://www.congress.gov/bill/{bill['congress']}th-congress/{'house' if bt=='hr' else 'senate'}-bill/{bn}",
                })
        except Exception as e:
            failures += 1
            print(f"  Bill error [{bill['name']}]: {e}")
    status = STATUS_FAILED if failures == len(bills) and bills else STATUS_OK
    detail = f"{len(updates)} bill updates"
    if failures:
        detail += f"; {failures} failures"
    mark_source("Congress", status, detail=detail, records=len(updates))
    return updates

