"""
Polymarket OSINT Monitor
Automated daily intelligence gathering on prediction markets,
regulatory developments, and suspicious activity.
"""

import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── CONFIG ──────────────────────────────────────────────────
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "shanabautista0819@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # Set in GitHub Secrets

TODAY = datetime.date.today().isoformat()

# ── RSS FEEDS ────────────────────────────────────────────────
RSS_FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "The Block": "https://www.theblock.co/rss.xml",
    "Decrypt": "https://decrypt.co/feed",
    "Bloomberg Crypto": "https://feeds.bloomberg.com/crypto/news.rss",
    "DLA Piper Market Edge": "https://marketedge.dlapiper.com/feed/",
    "CFTC Press Releases": "https://www.cftc.gov/rss/pressreleases.xml",
    "CFTC Enforcement Actions": "https://www.cftc.gov/rss/enforcementactions.xml",
}

# ── KEYWORDS TO MONITOR ──────────────────────────────────────
KEYWORDS = [
    "polymarket",
    "kalshi",
    "prediction market",
    "event contract",
    "CFTC prediction",
    "insider trading prediction",
    "binary option CFTC",
    "prediction market manipulation",
    "prediction market insider",
    "PREDICT act",
    "STOP corrupt bets",
    "BETS OFF act",
    "event contract enforcement",
    "prediction market regulation",
    "wash trading crypto",
    "UMA protocol",
    "oracle manipulation",
]

# ── CONGRESSIONAL BILLS TO TRACK ─────────────────────────────
BILLS = [
    {"name": "PREDICT Act", "id": "hr8076", "congress": "119"},
    {"name": "End Prediction Market Corruption Act", "id": "s4017", "congress": "119"},
    {"name": "Prediction Markets Security and Integrity Act", "id": "s4060", "congress": "119"},
    {"name": "Public Integrity in Financial Prediction Markets Act", "id": "s4188", "congress": "119"},
    {"name": "STOP Corrupt Bets Act", "id": "s4226", "congress": "119"},
    {"name": "BETS OFF Act", "id": "s4115", "congress": "119"},
    {"name": "Event Contract Enforcement Act", "id": "hr7840", "congress": "119"},
]

# ── TWITTER/X ACCOUNTS TO MONITOR ───────────────────────────
TWITTER_ACCOUNTS = [
    "@Polymarket",
    "@CFTCwatch",
    "@wassielawyer",
    "@0xfoobar",
]

def fetch_rss_alerts(feeds: dict, keywords: list) -> list:
    """Fetch RSS feeds and filter by keywords."""
    hits = []
    for source, url in feeds.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "").lower()
                summary = entry.get("summary", "").lower()
                combined = title + " " + summary
                matched = [kw for kw in keywords if kw.lower() in combined]
                if matched:
                    hits.append({
                        "source": source,
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "matched_keywords": matched,
                        "summary": entry.get("summary", "")[:300],
                    })
        except Exception as e:
            print(f"Error fetching {source}: {e}")
    return hits


def fetch_cftc_enforcement() -> list:
    """Scrape CFTC enforcement actions page for new actions."""
    hits = []
    try:
        url = "https://www.cftc.gov/LawRegulation/EnforcementActions/index.htm"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        # Find enforcement action links
        for link in soup.find_all("a", href=True)[:20]:
            text = link.get_text(strip=True).lower()
            if any(kw in text for kw in ["prediction", "polymarket", "kalshi", "binary", "event contract"]):
                hits.append({
                    "source": "CFTC Enforcement",
                    "title": link.get_text(strip=True),
                    "link": "https://www.cftc.gov" + link["href"] if link["href"].startswith("/") else link["href"],
                    "published": TODAY,
                    "matched_keywords": ["CFTC enforcement"],
                    "summary": "New CFTC enforcement action detected",
                })
    except Exception as e:
        print(f"Error fetching CFTC enforcement: {e}")
    return hits


def fetch_cftc_rulemaking() -> list:
    """Check CFTC for new no-action letters and rulemaking notices."""
    hits = []
    try:
        url = "https://www.cftc.gov/LawRegulation/CFTCStaffLetters/index.htm"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.find_all("a", href=True)[:10]:
            text = link.get_text(strip=True).lower()
            if any(kw in text for kw in ["prediction", "event contract", "polymarket", "kalshi"]):
                hits.append({
                    "source": "CFTC No-Action/Rulemaking",
                    "title": link.get_text(strip=True),
                    "link": "https://www.cftc.gov" + link["href"] if link["href"].startswith("/") else link["href"],
                    "published": TODAY,
                    "matched_keywords": ["CFTC rulemaking"],
                    "summary": "New CFTC no-action letter or rulemaking notice",
                })
    except Exception as e:
        print(f"Error fetching CFTC rulemaking: {e}")
    return hits


def check_congress_bills(bills: list) -> list:
    """Check Congress.gov API for bill status updates."""
    updates = []
    api_key = os.environ.get("CONGRESS_API_KEY", "")
    if not api_key:
        print("No Congress API key set — skipping bill tracking")
        return updates
    
    for bill in bills:
        try:
            bill_type = "hr" if bill["id"].startswith("hr") else "s"
            bill_number = bill["id"].replace("hr", "").replace("s", "")
            url = f"https://api.congress.gov/v3/bill/{bill['congress']}/{bill_type}/{bill_number}"
            response = requests.get(url, params={"api_key": api_key}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                bill_data = data.get("bill", {})
                updates.append({
                    "bill": bill["name"],
                    "id": bill["id"].upper(),
                    "title": bill_data.get("title", ""),
                    "latest_action": bill_data.get("latestAction", {}).get("text", "No action found"),
                    "action_date": bill_data.get("latestAction", {}).get("actionDate", ""),
                    "url": f"https://www.congress.gov/bill/{bill['congress']}th-congress/{'house' if bill_type == 'hr' else 'senate'}-bill/{bill_number}",
                })
        except Exception as e:
            print(f"Error checking {bill['name']}: {e}")
    return updates


def check_dune_polymarket() -> dict:
    """Fetch Polymarket on-chain stats from Dune Analytics public API."""
    stats = {}
    try:
        # Dune public query for Polymarket volume (query ID may need updating)
        # Using a known public Polymarket dashboard query
        url = "https://api.dune.com/api/v1/query/3258964/results"
        api_key = os.environ.get("DUNE_API_KEY", "")
        if api_key:
            headers = {"X-Dune-API-Key": api_key}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                stats["dune_data"] = data.get("result", {}).get("rows", [])[:5]
        else:
            stats["note"] = "No Dune API key set — set DUNE_API_KEY in GitHub Secrets"
    except Exception as e:
        stats["error"] = str(e)
    return stats


def save_report(all_hits: list, bill_updates: list, dune_stats: dict) -> str:
    """Save daily report to JSON and markdown."""
    report = {
        "date": TODAY,
        "total_alerts": len(all_hits),
        "alerts": all_hits,
        "bill_updates": bill_updates,
        "dune_stats": dune_stats,
    }
    
    # Save JSON
    json_path = f"output/report_{TODAY}.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    
    # Build markdown report
    md = f"""# Polymarket OSINT Daily Report
**Date:** {TODAY}
**Total Alerts:** {len(all_hits)}

---

## News & Regulatory Alerts

"""
    if all_hits:
        for hit in all_hits:
            md += f"### {hit['title']}\n"
            md += f"**Source:** {hit['source']} | **Published:** {hit.get('published', 'N/A')}\n\n"
            md += f"**Keywords matched:** {', '.join(hit['matched_keywords'])}\n\n"
            md += f"{hit.get('summary', '')}\n\n"
            md += f"[Read more]({hit.get('link', '')})\n\n---\n\n"
    else:
        md += "_No alerts today._\n\n"

    md += "## Congressional Bill Status\n\n"
    if bill_updates:
        for bill in bill_updates:
            md += f"### {bill['bill']} ({bill['id']})\n"
            md += f"**Latest Action:** {bill['latest_action']}\n\n"
            md += f"**Date:** {bill.get('action_date', 'N/A')}\n\n"
            md += f"[View on Congress.gov]({bill['url']})\n\n---\n\n"
    else:
        md += "_Bill tracking requires CONGRESS_API_KEY secret._\n\n"

    md_path = f"output/report_{TODAY}.md"
    with open(md_path, "w") as f:
        f.write(md)
    
    return md


def send_email_alert(report_md: str, num_alerts: int):
    """Send email digest if there are alerts."""
    if not SMTP_PASSWORD or num_alerts == 0:
        print(f"Skipping email: {num_alerts} alerts, password set: {bool(SMTP_PASSWORD)}")
        return
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Polymarket OSINT Report {TODAY} — {num_alerts} alerts"
    msg["From"] = ALERT_EMAIL
    msg["To"] = ALERT_EMAIL
    
    msg.attach(MIMEText(report_md, "plain"))
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ALERT_EMAIL, SMTP_PASSWORD)
            server.sendmail(ALERT_EMAIL, ALERT_EMAIL, msg.as_string())
        print("Email sent successfully")
    except Exception as e:
        print(f"Error sending email: {e}")


def main():
    print(f"Starting Polymarket OSINT Monitor — {TODAY}")
    
    # Fetch RSS alerts
    print("Fetching RSS feeds...")
    rss_hits = fetch_rss_alerts(RSS_FEEDS, KEYWORDS)
    print(f"Found {len(rss_hits)} RSS alerts")
    
    # Fetch CFTC enforcement
    print("Checking CFTC enforcement actions...")
    cftc_hits = fetch_cftc_enforcement()
    
    # Fetch CFTC rulemaking
    print("Checking CFTC rulemaking notices...")
    rulemaking_hits = fetch_cftc_rulemaking()
    
    # All news hits combined
    all_hits = rss_hits + cftc_hits + rulemaking_hits
    
    # Check congressional bills
    print("Checking congressional bill status...")
    bill_updates = check_congress_bills(BILLS)
    
    # Check Dune on-chain data
    print("Fetching Dune Analytics data...")
    dune_stats = check_dune_polymarket()
    
    # Save and send report
    print("Generating report...")
    report_md = save_report(all_hits, bill_updates, dune_stats)
    
    # Send email if alerts found
    send_email_alert(report_md, len(all_hits))
    
    print(f"Done. {len(all_hits)} alerts found.")
    print(report_md[:500])


if __name__ == "__main__":
    main()
