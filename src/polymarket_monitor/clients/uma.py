"""UMA governance RSS filtering."""

from __future__ import annotations

import datetime
import email.utils
import logging
from typing import Any

import feedparser

from polymarket_monitor.clients.rss import clean_text, parse_date
from polymarket_monitor.source_status import STATUS_FAILED, STATUS_OK, get_source_status, mark_source

logger = logging.getLogger(__name__)


def fetch_uma_governance() -> list[dict[str, Any]]:
    alerts = []
    cutoff_date = datetime.date.today() - datetime.timedelta(days=14)
    abuse_terms = [
        "bad-faith p4", "bad faith p4", "coordinated bad-faith",
        "governance attack", "incorrect resolution", "call for slashing",
    ]
    try:
        feed = feedparser.parse("https://discourse.uma.xyz/latest.rss")
        for entry in feed.entries[:30]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            combined = (title + " " + summary).lower()

            raw_date = entry.get("published", "")
            try:
                parsed_dt = email.utils.parsedate_to_datetime(raw_date)
                if parsed_dt.date() < cutoff_date:
                    continue
            except Exception:
                pass

            mentions_polymarket = "polymarket" in combined
            type1 = (
                mentions_polymarket
                and any(w in combined for w in ["dispute", "incorrect", "contested", "slashing", "bad-faith", "bad faith", "p4", "resolution"])
                and any(w in combined for w in ["market", "outcome", "resolved", "vote", "voter"])
            )
            type2 = any(term in combined for term in abuse_terms)
            if not type1 and not type2:
                continue

            alert_type = "POLYMARKET DISPUTE" if type1 else "GOVERNANCE ABUSE"
            note = (
                "Active Polymarket resolution dispute — check if any voter holds a position in this market."
                if type1 else
                "Explicit governance abuse pattern — affects resolution integrity across Polymarket markets."
            )
            alerts.append({
                "title": title,
                "link": entry.get("link", ""),
                "published": parse_date(raw_date),
                "summary": clean_text(summary)[:200],
                "note": note,
                "alert_type": alert_type,
            })
    except Exception as e:
        logger.warning("UMA governance collection failed: %s", e)
        mark_source("UMA", STATUS_FAILED, detail=str(e), records=0)
        print(f"  UMA error: {e}")

    if "UMA" not in get_source_status():
        mark_source("UMA", STATUS_OK, detail=f"{len(alerts)} alerts", records=len(alerts))
    print(f"  UMA alerts (last 14 days, strict): {len(alerts)}")
    return alerts

