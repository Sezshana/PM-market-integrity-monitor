"""
Polymarket OSINT Monitor
Clean daily digest — TL;DR summaries, big news first.
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

ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "shanabautista0819@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
TODAY = datetime.date.today().isoformat()
TODAY_PRETTY = datetime.date.today().strftime("%B %d, %Y")

RSS_FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "The Block": "https://www.theblock.co/rss.xml",
    "Decrypt": "https://decrypt.co/feed",
    "DLA Piper Market Edge": "https://marketedge.dlapiper.com/feed/",
    "CFTC Press Releases": "https://www.cftc.gov/rss/pressreleases.xml",
    "CFTC Enforcement Actions": "https://www.cftc.gov/rss/enforcementactions.xml",
}

KEYWORDS = [
    "polymarket", "kalshi", "prediction market", "event contract",
    "CFTC prediction", "insider trading prediction", "binary option CFTC",
    "prediction market manipulation", "prediction market insider",
    "PREDICT act", "STOP corrupt bets", "BETS OFF act",
    "event contract enforcement", "wash trading crypto",
    "UMA protocol", "oracle manipulation", "prediction market regulation",
]

HIGH_PRIORITY_KEYWORDS = [
    "polymarket", "kalshi", "insider trading prediction",
    "prediction market manipulation", "CFTC enforcement",
    "oracle manipulation", "UMA protocol",
]

BILLS = [
    {"name": "PREDICT Act", "id": "hr8076", "congress": "119"},
    {"name": "End Prediction Market Corruption Act", "id": "s4017", "congress": "119"},
    {"name": "Prediction Markets Security and Integrity Act", "id": "s4060", "congress": "119"},
    {"name": "Public Integrity in Financial Prediction Markets Act", "id": "s4188", "congress": "119"},
    {"name": "STOP Corrupt Bets Act", "id": "s4226", "congress": "119"},
    {"name": "BETS OFF Act", "id": "s4115", "congress": "119"},
    {"name": "Event Contract Enforcement Act", "id": "hr7840", "congress": "119"},
]


def fetch_rss_alerts(feeds, keywords):
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
                    priority = any(kw.lower() in combined for kw in HIGH_PRIORITY_KEYWORDS)
                    # Clean summary — strip HTML
                    raw_summary = entry.get("summary", "")
                    clean_summary = BeautifulSoup(raw_summary, "html.parser").get_text()
                    clean_summary = " ".join(clean_summary.split())[:200]
                    hits.append({
                        "source": source,
                        "title": entry.get("title", "No title"),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "matched_keywords": matched,
                        "summary": clean_summary,
                        "priority": priority,
                    })
        except Exception as e:
            print(f"Error fetching {source}: {e}")
    return hits


def check_congress_bills(bills):
    updates = []
    api_key = os.environ.get("CONGRESS_API_KEY", "")
    if not api_key:
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
                    "latest_action": bill_data.get("latestAction", {}).get("text", "No action found"),
                    "action_date": bill_data.get("latestAction", {}).get("actionDate", ""),
                    "url": f"https://www.congress.gov/bill/{bill['congress']}th-congress/{'house' if bill_type == 'hr' else 'senate'}-bill/{bill_number}",
                })
        except Exception as e:
            print(f"Error checking {bill['name']}: {e}")
    return updates


def build_email(all_hits, bill_updates):
    """Build a clean, scannable digest email."""
    high = [h for h in all_hits if h["priority"]]
    normal = [h for h in all_hits if not h["priority"]]

    lines = []
    lines.append(f"POLYMARKET OSINT DAILY DIGEST — {TODAY_PRETTY}")
    lines.append("=" * 60)
    lines.append("")

    # ── QUICK SUMMARY ──
    lines.append("AT A GLANCE")
    lines.append("-" * 40)
    lines.append(f"Total alerts today:     {len(all_hits)}")
    lines.append(f"High priority:          {len(high)}")
    lines.append(f"General news:           {len(normal)}")
    lines.append(f"Bills tracked:          {len(BILLS)}")
    lines.append("")

    # ── HIGH PRIORITY ──
    if high:
        lines.append("HIGH PRIORITY — READ THESE FIRST")
        lines.append("=" * 60)
        for i, item in enumerate(high, 1):
            lines.append(f"\n{i}. {item['title']}")
            lines.append(f"   Source: {item['source']}")
            lines.append(f"   TL;DR:  {item['summary']}")
            lines.append(f"   Link:   {item['link']}")
            lines.append(f"   Keywords matched: {', '.join(item['matched_keywords'])}")
    else:
        lines.append("HIGH PRIORITY")
        lines.append("-" * 40)
        lines.append("No high priority alerts today.")

    lines.append("")

    # ── GENERAL NEWS ──
    if normal:
        lines.append("GENERAL NEWS & REGULATORY UPDATES")
        lines.append("=" * 60)
        for i, item in enumerate(normal, 1):
            lines.append(f"\n{i}. {item['title']}")
            lines.append(f"   Source: {item['source']}")
            lines.append(f"   TL;DR:  {item['summary']}")
            lines.append(f"   Link:   {item['link']}")
    else:
        lines.append("GENERAL NEWS")
        lines.append("-" * 40)
        lines.append("No general alerts today.")

    lines.append("")

    # ── CONGRESSIONAL BILLS ──
    lines.append("CONGRESSIONAL BILL TRACKER")
    lines.append("=" * 60)
    if bill_updates:
        for bill in bill_updates:
            lines.append(f"\n{bill['bill']} ({bill['id']})")
            lines.append(f"   Latest: {bill['latest_action']}")
            lines.append(f"   Date:   {bill.get('action_date', 'N/A')}")
            lines.append(f"   Link:   {bill['url']}")
    else:
        lines.append("Add CONGRESS_API_KEY to GitHub Secrets to enable bill tracking.")

    lines.append("")
    lines.append("=" * 60)
    lines.append("Polymarket OSINT Monitor — runs daily at 8 AM EST")
    lines.append("Repo: github.com/Sezshana/polymarket-osint-monitor")

    return "\n".join(lines)


def save_report(all_hits, bill_updates):
    report = {
        "date": TODAY,
        "total_alerts": len(all_hits),
        "high_priority": len([h for h in all_hits if h["priority"]]),
        "alerts": all_hits,
        "bill_updates": bill_updates,
    }
    os.makedirs("output", exist_ok=True)
    with open(f"output/report_{TODAY}.json", "w") as f:
        json.dump(report, f, indent=2)
    email_body = build_email(all_hits, bill_updates)
    with open(f"output/report_{TODAY}.md", "w") as f:
        f.write(email_body)
    return email_body


def send_email(body, num_alerts):
    if not SMTP_PASSWORD:
        print("No SMTP password — skipping email")
        return
    subject = f"Polymarket Digest {TODAY_PRETTY} — {num_alerts} alerts"
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = ALERT_EMAIL
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ALERT_EMAIL, SMTP_PASSWORD)
            server.sendmail(ALERT_EMAIL, ALERT_EMAIL, msg.as_string())
        print("Email sent")
    except Exception as e:
        print(f"Email error: {e}")


def main():
    print(f"Starting Polymarket OSINT Monitor — {TODAY}")
    print("Fetching RSS feeds...")
    all_hits = fetch_rss_alerts(RSS_FEEDS, KEYWORDS)
    print(f"Found {len(all_hits)} alerts ({len([h for h in all_hits if h['priority']])} high priority)")
    print("Checking congressional bills...")
    bill_updates = check_congress_bills(BILLS)
    print("Generating report...")
    body = save_report(all_hits, bill_updates)
    send_email(body, len(all_hits))
    print("Done.")
    print(body[:300])


if __name__ == "__main__":
    main()
