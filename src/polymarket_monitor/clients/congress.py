"""Congress.gov bill tracking client."""

from __future__ import annotations

from typing import Any

import requests

from polymarket_monitor import config


def check_congress_bills(bills: list[dict[str, str]]) -> list[dict[str, Any]]:
    updates = []
    if not config.CONGRESS_KEY:
        return updates
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
            print(f"  Bill error [{bill['name']}]: {e}")
    return updates

