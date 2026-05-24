"""
Polymarket OSINT Monitor v4
Full suite: deduplication, large trade detection, wallet watchlist,
UMA governance monitoring, OFAC cross-reference, weekly summary,
win rate tracker, case index, and clean digest email.
"""

import os
import json
import datetime
import re
import csv
import requests
from bs4 import BeautifulSoup
import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# ── CONFIG ───────────────────────────────────────────────────
ALERT_EMAIL   = os.environ.get("ALERT_EMAIL", "shanabautista0819@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
DUNE_API_KEY  = os.environ.get("DUNE_API_KEY", "")
CONGRESS_KEY  = os.environ.get("CONGRESS_API_KEY", "")

TODAY         = datetime.date.today().isoformat()
TODAY_PRETTY  = datetime.date.today().strftime("%B %d, %Y")
WEEKDAY       = datetime.date.today().weekday()  # 6 = Sunday

# Folders
Path("output").mkdir(exist_ok=True)
Path("cases").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)

# ── SOURCE PRIORITY ──────────────────────────────────────────
SOURCE_PRIORITY = {
    "CFTC Enforcement Actions": 10,
    "CFTC Press Releases": 9,
    "DLA Piper Market Edge": 8,
    "Bloomberg Crypto": 7,
    "CoinDesk": 6,
    "The Block": 5,
    "Decrypt": 4,
}

RSS_FEEDS = {
    "CoinDesk":               "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "The Block":              "https://www.theblock.co/rss.xml",
    "Decrypt":                "https://decrypt.co/feed",
    "DLA Piper Market Edge":  "https://marketedge.dlapiper.com/feed/",
    "CFTC Press Releases":    "https://www.cftc.gov/rss/pressreleases.xml",
    "CFTC Enforcement Actions": "https://www.cftc.gov/rss/enforcementactions.xml",
}

KEYWORDS = [
    "polymarket","kalshi","prediction market","event contract",
    "CFTC prediction","insider trading prediction","binary option CFTC",
    "prediction market manipulation","prediction market insider",
    "PREDICT act","STOP corrupt bets","BETS OFF act",
    "event contract enforcement","wash trading crypto",
    "UMA protocol","oracle manipulation","prediction market regulation",
]

HIGH_PRIORITY_KEYWORDS = [
    "polymarket","kalshi","insider trading prediction",
    "prediction market manipulation","CFTC enforcement",
    "oracle manipulation","UMA protocol",
]

BILLS = [
    {"name": "PREDICT Act",                                  "id": "hr8076", "congress": "119"},
    {"name": "End Prediction Market Corruption Act",         "id": "s4017",  "congress": "119"},
    {"name": "Prediction Markets Security and Integrity Act","id": "s4060",  "congress": "119"},
    {"name": "Public Integrity in Financial Prediction Markets Act","id": "s4188","congress": "119"},
    {"name": "STOP Corrupt Bets Act",                       "id": "s4226",  "congress": "119"},
    {"name": "BETS OFF Act",                                 "id": "s4115",  "congress": "119"},
    {"name": "Event Contract Enforcement Act",               "id": "hr7840", "congress": "119"},
]

# ── THRESHOLDS ───────────────────────────────────────────────
LARGE_TRADE_MIN_USD    = 10_000   # Flag trades over $10k
LOW_PROB_MAX_PCT       = 15       # On markets under 15% probability
WIN_RATE_ALERT_PCT     = 75       # Flag wallets winning >75% on long shots


# ════════════════════════════════════════════════════════════
# 1. DEDUPLICATION
# ════════════════════════════════════════════════════════════

def clean_text(html):
    text = BeautifulSoup(html or "", "html.parser").get_text()
    return " ".join(text.split())

def title_fingerprint(title):
    stopwords = {
        "a","an","the","and","or","but","in","on","at","to","for","of",
        "with","by","from","is","are","was","were","it","its","as","be",
        "has","have","had","will","that","this","these","those","their",
        "they","how","what","when","where","who","why","which","not","no",
        "new","says","say","over","up","down","after","before","than",
        "more","first","into","its","about","would","could","should",
    }
    words = re.sub(r"[^a-z0-9\s]", "", title.lower()).split()
    significant = sorted([w for w in words if w not in stopwords and len(w) > 2])
    return " ".join(significant[:6])

def stories_are_similar(a, b):
    fa = set(title_fingerprint(a).split())
    fb = set(title_fingerprint(b).split())
    if not fa or not fb:
        return False
    return len(fa & fb) / len(fa | fb) >= 0.5

def deduplicate(hits):
    clusters = []
    for hit in hits:
        placed = False
        for cluster in clusters:
            if stories_are_similar(hit["title"], cluster[0]["title"]):
                cluster.append(hit)
                placed = True
                break
        if not placed:
            clusters.append([hit])
    result = []
    for cluster in clusters:
        best = sorted(cluster, key=lambda x: SOURCE_PRIORITY.get(x["source"], 0), reverse=True)[0]
        others = list(set(c["source"] for c in cluster if c["source"] != best["source"]))
        best["also_covered_by"] = others
        result.append(best)
    return result


# ════════════════════════════════════════════════════════════
# 2. RSS FEED MONITORING
# ════════════════════════════════════════════════════════════

def fetch_rss(feeds, keywords):
    raw = []
    for source, url in feeds.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title   = entry.get("title", "").lower()
                summary = entry.get("summary", "").lower()
                combined = title + " " + summary
                matched = [kw for kw in keywords if kw.lower() in combined]
                if matched:
                    priority = any(kw.lower() in combined for kw in HIGH_PRIORITY_KEYWORDS)

                    # Check watchlist
                    watchlist_hit = check_watchlist_match(entry.get("title","") + " " + entry.get("summary",""))

                    raw.append({
                        "source":         source,
                        "title":          entry.get("title", "No title"),
                        "link":           entry.get("link", ""),
                        "published":      entry.get("published", ""),
                        "matched_keywords": matched,
                        "summary":        clean_text(entry.get("summary",""))[:220],
                        "priority":       priority or bool(watchlist_hit),
                        "watchlist_hit":  watchlist_hit,
                        "also_covered_by": [],
                    })
        except Exception as e:
            print(f"  RSS error [{source}]: {e}")
    deduped = deduplicate(raw)
    print(f"  RSS: {len(raw)} raw → {len(deduped)} unique stories")
    return deduped


# ════════════════════════════════════════════════════════════
# 3. WATCHLIST
# ════════════════════════════════════════════════════════════

def load_watchlist():
    """Load keywords, wallets, and handles from watchlist.txt"""
    path = Path("watchlist.txt")
    if not path.exists():
        return {"keywords": [], "wallets": [], "handles": []}
    keywords, wallets, handles = [], [], []
    current_section = None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].lower()
        elif current_section == "keywords":
            keywords.append(line.lower())
        elif current_section == "wallets":
            wallets.append(line.lower())
        elif current_section == "handles":
            handles.append(line.lower().lstrip("@"))
    return {"keywords": keywords, "wallets": wallets, "handles": handles}

WATCHLIST = load_watchlist()

def check_watchlist_match(text):
    """Return matched watchlist terms if any, else empty list."""
    text_lower = text.lower()
    hits = []
    for kw in WATCHLIST["keywords"]:
        if kw in text_lower:
            hits.append(f"keyword:{kw}")
    for wallet in WATCHLIST["wallets"]:
        if wallet in text_lower:
            hits.append(f"wallet:{wallet}")
    return hits


# ════════════════════════════════════════════════════════════
# 4. LARGE TRADE DETECTION (DUNE ANALYTICS)
# ════════════════════════════════════════════════════════════

def fetch_large_trades():
    """
    Query Dune for large Polymarket trades on low-probability markets.
    Requires DUNE_API_KEY. Uses a public Polymarket trades query.
    """
    if not DUNE_API_KEY:
        print("  Dune: no API key — skipping large trade detection")
        return []

    flagged = []
    try:
        # Execute query — Dune query 3258964 tracks Polymarket trades
        url = "https://api.dune.com/api/v1/query/3258964/execute"
        headers = {"X-Dune-API-Key": DUNE_API_KEY, "Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json={}, timeout=15)
        if resp.status_code != 200:
            print(f"  Dune execute error: {resp.status_code}")
            return []

        execution_id = resp.json().get("execution_id")
        if not execution_id:
            return []

        # Poll for results
        import time
        for _ in range(10):
            time.sleep(3)
            result_url = f"https://api.dune.com/api/v1/execution/{execution_id}/results"
            result = requests.get(result_url, headers=headers, timeout=15)
            if result.status_code == 200:
                rows = result.json().get("result", {}).get("rows", [])
                for row in rows:
                    amount = float(row.get("amount_usd", 0) or 0)
                    prob   = float(row.get("outcome_price", 1) or 1) * 100
                    wallet = row.get("trader", "unknown")
                    market = row.get("market_question", "unknown")
                    if amount >= LARGE_TRADE_MIN_USD and prob <= LOW_PROB_MAX_PCT:
                        flagged.append({
                            "wallet":   wallet,
                            "market":   market,
                            "amount":   amount,
                            "probability_pct": round(prob, 1),
                            "date":     row.get("block_date", TODAY),
                        })
                        update_win_rate_tracker(wallet, market, prob, amount)
                break
    except Exception as e:
        print(f"  Dune error: {e}")

    print(f"  Large trades flagged: {len(flagged)}")
    return flagged


# ════════════════════════════════════════════════════════════
# 5. WIN RATE TRACKER
# ════════════════════════════════════════════════════════════

WIN_RATE_FILE = Path("data/win_rate_tracker.json")

def load_win_rate():
    if WIN_RATE_FILE.exists():
        return json.loads(WIN_RATE_FILE.read_text())
    return {}

def save_win_rate(data):
    WIN_RATE_FILE.write_text(json.dumps(data, indent=2))

def update_win_rate_tracker(wallet, market, probability_pct, amount_usd):
    """Log a suspicious trade for win rate tracking."""
    data = load_win_rate()
    if wallet not in data:
        data[wallet] = {"trades": [], "wins": 0, "total": 0}
    data[wallet]["trades"].append({
        "date":            TODAY,
        "market":          market,
        "probability_pct": probability_pct,
        "amount_usd":      amount_usd,
        "resolved":        None,
        "won":             None,
    })
    data[wallet]["total"] += 1
    save_win_rate(data)

def get_win_rate_alerts():
    """Find wallets with suspiciously high win rates on long shots."""
    data = load_win_rate()
    alerts = []
    for wallet, stats in data.items():
        resolved = [t for t in stats["trades"] if t["won"] is not None]
        if len(resolved) >= 3:
            wins = sum(1 for t in resolved if t["won"])
            rate = wins / len(resolved) * 100
            if rate >= WIN_RATE_ALERT_PCT:
                alerts.append({
                    "wallet":       wallet,
                    "win_rate_pct": round(rate, 1),
                    "total_trades": len(resolved),
                    "wins":         wins,
                })
    return alerts


# ════════════════════════════════════════════════════════════
# 6. UMA GOVERNANCE MONITOR
# ════════════════════════════════════════════════════════════

def fetch_uma_governance():
    """
    Check UMA governance forum for new resolution disputes.
    Flags if a dispute voter also holds a market position (requires manual follow-up).
    """
    alerts = []
    try:
        # UMA Discourse forum RSS
        url = "https://discourse.uma.xyz/latest.rss"
        feed = feedparser.parse(url)
        for entry in feed.entries[:20]:
            title   = entry.get("title", "").lower()
            summary = entry.get("summary", "").lower()
            combined = title + " " + summary
            dispute_keywords = ["dispute","resolution","polymarket","settle","vote","invalid","incorrect"]
            if any(kw in combined for kw in dispute_keywords):
                alerts.append({
                    "title":     entry.get("title",""),
                    "link":      entry.get("link",""),
                    "published": entry.get("published",""),
                    "summary":   clean_text(entry.get("summary",""))[:200],
                    "note":      "REVIEW: Check if any dispute participant holds a position in this market.",
                })
    except Exception as e:
        print(f"  UMA governance error: {e}")
    print(f"  UMA governance alerts: {len(alerts)}")
    return alerts


# ════════════════════════════════════════════════════════════
# 7. OFAC CROSS-REFERENCE
# ════════════════════════════════════════════════════════════

OFAC_CACHE_FILE = Path("data/ofac_cache.json")

def fetch_ofac_additions():
    """
    Check OFAC SDN list for new crypto wallet additions.
    Compares against cached version to find what's new today.
    """
    new_entries = []
    try:
        url = "https://www.treasury.gov/ofac/downloads/sdn.xml"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  OFAC fetch error: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "xml")
        current = {}
        for entry in soup.find_all("sdnEntry"):
            uid  = entry.find("uid")
            name = entry.find("lastName")
            if uid and name:
                # Look for digital currency identifiers
                ids = entry.find_all("id")
                for id_tag in ids:
                    id_type = id_tag.find("idType")
                    id_num  = id_tag.find("idNumber")
                    if id_type and id_num and "Digital" in (id_type.text or ""):
                        current[uid.text] = {
                            "name":    name.text,
                            "wallet":  id_num.text,
                            "added":   TODAY,
                        }

        # Compare against cache
        cached = {}
        if OFAC_CACHE_FILE.exists():
            cached = json.loads(OFAC_CACHE_FILE.read_text())

        for uid, entry in current.items():
            if uid not in cached:
                new_entries.append(entry)

        # Save updated cache
        OFAC_CACHE_FILE.write_text(json.dumps(current, indent=2))

    except Exception as e:
        print(f"  OFAC error: {e}")

    print(f"  OFAC new crypto additions: {len(new_entries)}")
    return new_entries


# ════════════════════════════════════════════════════════════
# 8. CONGRESSIONAL BILL TRACKER
# ════════════════════════════════════════════════════════════

def check_congress_bills(bills):
    updates = []
    if not CONGRESS_KEY:
        return updates
    for bill in bills:
        try:
            bill_type   = "hr" if bill["id"].startswith("hr") else "s"
            bill_number = bill["id"].replace("hr","").replace("s","")
            url = f"https://api.congress.gov/v3/bill/{bill['congress']}/{bill_type}/{bill_number}"
            resp = requests.get(url, params={"api_key": CONGRESS_KEY}, timeout=10)
            if resp.status_code == 200:
                data      = resp.json()
                bill_data = data.get("bill", {})
                updates.append({
                    "bill":          bill["name"],
                    "id":            bill["id"].upper(),
                    "latest_action": bill_data.get("latestAction",{}).get("text","No action found"),
                    "action_date":   bill_data.get("latestAction",{}).get("actionDate",""),
                    "url": f"https://www.congress.gov/bill/{bill['congress']}th-congress/{'house' if bill_type=='hr' else 'senate'}-bill/{bill_number}",
                })
        except Exception as e:
            print(f"  Bill error [{bill['name']}]: {e}")
    return updates


# ════════════════════════════════════════════════════════════
# 9. CASE INDEX AUTO-GENERATOR
# ════════════════════════════════════════════════════════════

def update_case_index():
    """Scan the cases/ folder and regenerate the case index markdown."""
    case_files = sorted(Path("cases").glob("*.md"), reverse=True)
    lines = ["# Polymarket Investigation Case Index", f"_Last updated: {TODAY}_", ""]
    lines.append(f"**Total cases: {len(case_files)}**")
    lines.append("")
    lines.append("| Date | Case | File |")
    lines.append("|------|------|------|")
    for f in case_files:
        # Try to extract first line as title
        try:
            first_line = f.read_text().split("\n")[0].lstrip("# ").strip()
        except:
            first_line = f.stem
        date_part = f.stem[:10] if len(f.stem) >= 10 else f.stem
        lines.append(f"| {date_part} | {first_line} | [{f.name}](cases/{f.name}) |")

    Path("cases/INDEX.md").write_text("\n".join(lines))
    print(f"  Case index updated: {len(case_files)} cases")


# ════════════════════════════════════════════════════════════
# 10. WEEKLY SUMMARY (runs Sundays)
# ════════════════════════════════════════════════════════════

def generate_weekly_summary():
    """Look back at the last 7 days of reports and identify patterns."""
    if WEEKDAY != 6:
        return None

    print("  Generating weekly summary (Sunday)...")
    week_hits  = []
    topic_freq = {}
    source_freq= {}

    for i in range(7):
        date = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        report_path = Path(f"output/report_{date}.json")
        if report_path.exists():
            data = json.loads(report_path.read_text())
            for hit in data.get("alerts", []):
                week_hits.append(hit)
                for kw in hit.get("matched_keywords", []):
                    topic_freq[kw] = topic_freq.get(kw, 0) + 1
                source_freq[hit["source"]] = source_freq.get(hit["source"], 0) + 1

    top_topics  = sorted(topic_freq.items(),  key=lambda x: x[1], reverse=True)[:5]
    top_sources = sorted(source_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    win_alerts = get_win_rate_alerts()

    lines = [
        f"# Weekly Summary — Week ending {TODAY_PRETTY}",
        "",
        f"**Total unique stories this week:** {len(week_hits)}",
        "",
        "## Top Topics This Week",
    ]
    for topic, count in top_topics:
        lines.append(f"- {topic}: {count} stories")

    lines += ["", "## Most Active Sources"]
    for source, count in top_sources:
        lines.append(f"- {source}: {count} stories")

    if win_alerts:
        lines += ["", "## Win Rate Alerts (Suspicious Wallets)"]
        for alert in win_alerts:
            lines.append(f"- Wallet {alert['wallet']}: {alert['win_rate_pct']}% win rate across {alert['total_trades']} trades")

    summary_path = Path(f"output/weekly_summary_{TODAY}.md")
    summary_path.write_text("\n".join(lines))
    print(f"  Weekly summary saved: {summary_path}")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 11. EMAIL BUILDER
# ════════════════════════════════════════════════════════════

def build_email(news_hits, large_trades, uma_alerts, ofac_new, bill_updates, win_alerts, weekly=None):
    high   = [h for h in news_hits if h["priority"]]
    normal = [h for h in news_hits if not h["priority"]]
    lines  = []

    lines.append(f"POLYMARKET OSINT DAILY DIGEST — {TODAY_PRETTY}")
    lines.append("=" * 60)
    lines.append("")

    # AT A GLANCE
    lines.append("AT A GLANCE")
    lines.append("-" * 40)
    lines.append(f"Unique news stories:    {len(news_hits)}")
    lines.append(f"High priority:          {len(high)}")
    lines.append(f"Large trades flagged:   {len(large_trades)}")
    lines.append(f"UMA governance alerts:  {len(uma_alerts)}")
    lines.append(f"New OFAC crypto adds:   {len(ofac_new)}")
    lines.append(f"Win rate alerts:        {len(win_alerts)}")
    lines.append(f"Bills tracked:          {len(BILLS)}")
    if weekly:
        lines.append(f"Weekly summary:         YES — see bottom")
    lines.append("")

    # LARGE TRADE ALERTS
    if large_trades:
        lines.append("LARGE TRADE ALERTS — INVESTIGATE THESE")
        lines.append("=" * 60)
        for t in large_trades:
            lines.append(f"\nWallet: {t['wallet']}")
            lines.append(f"  Market:      {t['market']}")
            lines.append(f"  Amount:      ${t['amount']:,.0f}")
            lines.append(f"  Probability: {t['probability_pct']}% at time of trade")
            lines.append(f"  Date:        {t['date']}")
            lines.append(f"  ACTION:      Run wallet OSINT. Check UMA governance. Trace funding source.")
            wl_hit = check_watchlist_match(t["wallet"] + " " + t["market"])
            if wl_hit:
                lines.append(f"  WATCHLIST:   {', '.join(wl_hit)}")
    lines.append("")

    # UMA GOVERNANCE
    if uma_alerts:
        lines.append("UMA GOVERNANCE / ORACLE DISPUTES")
        lines.append("=" * 60)
        for a in uma_alerts:
            lines.append(f"\n{a['title']}")
            lines.append(f"  {a['summary']}")
            lines.append(f"  Link:  {a['link']}")
            lines.append(f"  NOTE:  {a['note']}")
    lines.append("")

    # OFAC
    if ofac_new:
        lines.append("NEW OFAC CRYPTO SANCTIONS — CROSS-REFERENCE WITH POLYMARKET")
        lines.append("=" * 60)
        for o in ofac_new:
            lines.append(f"\n{o['name']}")
            lines.append(f"  Wallet: {o['wallet']}")
            lines.append(f"  ACTION: Check this wallet against Polymarket trading history.")
    lines.append("")

    # WIN RATE ALERTS
    if win_alerts:
        lines.append("WIN RATE TRACKER ALERTS")
        lines.append("=" * 60)
        for a in win_alerts:
            lines.append(f"\nWallet: {a['wallet']}")
            lines.append(f"  Win rate: {a['win_rate_pct']}% across {a['total_trades']} tracked trades")
            lines.append(f"  ACTION:   Full OSINT investigation recommended.")
    lines.append("")

    # HIGH PRIORITY NEWS
    if high:
        lines.append("HIGH PRIORITY NEWS — READ THESE FIRST")
        lines.append("=" * 60)
        for i, item in enumerate(high, 1):
            lines.append(f"\n{i}. {item['title']}")
            lines.append(f"   Source:  {item['source']}")
            if item.get("also_covered_by"):
                lines.append(f"   Also in: {', '.join(item['also_covered_by'])}")
            if item.get("watchlist_hit"):
                lines.append(f"   WATCHLIST HIT: {', '.join(item['watchlist_hit'])}")
            lines.append(f"   TL;DR:   {item['summary']}")
            lines.append(f"   Link:    {item['link']}")
    lines.append("")

    # GENERAL NEWS
    if normal:
        lines.append("GENERAL NEWS & REGULATORY UPDATES")
        lines.append("=" * 60)
        for i, item in enumerate(normal, 1):
            lines.append(f"\n{i}. {item['title']}")
            lines.append(f"   Source:  {item['source']}")
            if item.get("also_covered_by"):
                lines.append(f"   Also in: {', '.join(item['also_covered_by'])}")
            lines.append(f"   TL;DR:   {item['summary']}")
            lines.append(f"   Link:    {item['link']}")
    lines.append("")

    # CONGRESSIONAL BILLS
    lines.append("CONGRESSIONAL BILL TRACKER")
    lines.append("=" * 60)
    if bill_updates:
        for bill in bill_updates:
            lines.append(f"\n{bill['bill']} ({bill['id']})")
            lines.append(f"   Latest: {bill['latest_action']}")
            lines.append(f"   Date:   {bill.get('action_date','N/A')}")
            lines.append(f"   Link:   {bill['url']}")
    else:
        lines.append("Add CONGRESS_API_KEY to GitHub Secrets to enable bill tracking.")
    lines.append("")

    # WEEKLY SUMMARY
    if weekly:
        lines.append("WEEKLY SUMMARY")
        lines.append("=" * 60)
        lines.append(weekly)
        lines.append("")

    lines.append("=" * 60)
    lines.append(f"Polymarket OSINT Monitor v4 — runs daily at 8 AM EST")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 12. SAVE + SEND
# ════════════════════════════════════════════════════════════

def save_report(news_hits, large_trades, uma_alerts, ofac_new, bill_updates, win_alerts, weekly):
    report = {
        "date":                TODAY,
        "unique_news_stories": len(news_hits),
        "large_trades_flagged":len(large_trades),
        "uma_alerts":          len(uma_alerts),
        "ofac_new":            len(ofac_new),
        "alerts":              news_hits,
        "large_trades":        large_trades,
        "uma_governance":      uma_alerts,
        "ofac_additions":      ofac_new,
        "bill_updates":        bill_updates,
    }
    with open(f"output/report_{TODAY}.json","w") as f:
        json.dump(report, f, indent=2)
    body = build_email(news_hits, large_trades, uma_alerts, ofac_new, bill_updates, win_alerts, weekly)
    with open(f"output/report_{TODAY}.md","w") as f:
        f.write(body)
    return body

def send_email(body, num_alerts):
    if not SMTP_PASSWORD:
        print("No SMTP password — skipping email")
        return
    total = num_alerts
    subject = f"Polymarket Digest {TODAY_PRETTY} — {total} stories"
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"]    = ALERT_EMAIL
    msg["To"]      = ALERT_EMAIL
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ALERT_EMAIL, SMTP_PASSWORD)
            server.sendmail(ALERT_EMAIL, ALERT_EMAIL, msg.as_string())
        print("Email sent")
    except Exception as e:
        print(f"Email error: {e}")


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def main():
    print(f"Polymarket OSINT Monitor v4 — {TODAY}")

    print("1. Fetching RSS feeds...")
    news_hits = fetch_rss(RSS_FEEDS, KEYWORDS)

    print("2. Checking large trades (Dune)...")
    large_trades = fetch_large_trades()

    print("3. Monitoring UMA governance...")
    uma_alerts = fetch_uma_governance()

    print("4. Checking OFAC sanctions list...")
    ofac_new = fetch_ofac_additions()

    print("5. Tracking congressional bills...")
    bill_updates = check_congress_bills(BILLS)

    print("6. Checking win rate tracker...")
    win_alerts = get_win_rate_alerts()

    print("7. Updating case index...")
    update_case_index()

    print("8. Weekly summary check...")
    weekly = generate_weekly_summary()

    print("9. Saving report and sending email...")
    body = save_report(news_hits, large_trades, uma_alerts, ofac_new, bill_updates, win_alerts, weekly)
    send_email(body, len(news_hits))

    print(f"Done. {len(news_hits)} stories, {len(large_trades)} trade alerts, {len(uma_alerts)} UMA alerts.")


if __name__ == "__main__":
    main()
