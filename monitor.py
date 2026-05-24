"""
Polymarket OSINT Monitor v5
Fixes: OFAC noise, UMA noise, empty TL;DRs
New: Polymarket API trade scraper, suspicious trade detection
"""

import os
import json
import datetime
import re
import time
import requests
from bs4 import BeautifulSoup
import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

ALERT_EMAIL   = os.environ.get("ALERT_EMAIL", "shanabautista0819@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
CONGRESS_KEY  = os.environ.get("CONGRESS_API_KEY", "")
DUNE_API_KEY  = os.environ.get("DUNE_API_KEY", "")

TODAY        = datetime.date.today().isoformat()
TODAY_PRETTY = datetime.date.today().strftime("%B %d, %Y")
WEEKDAY      = datetime.date.today().weekday()

for folder in ["output", "cases", "data"]:
    Path(folder).mkdir(exist_ok=True)

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

# UMA forum posts must match these to be included — much stricter than before
UMA_REQUIRED_KEYWORDS = [
    "polymarket", "dispute", "resolution", "incorrect", "manipulat",
    "bad faith", "exploit", "governance attack", "slashing", "bad-faith"
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

LARGE_TRADE_USD  = 10_000
LOW_PROB_MAX_PCT = 15
WIN_RATE_ALERT   = 75


# ════════════════════════════════════════════════════════════
# UTILITIES
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
        "more","first","into","about","would","could","should",
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

def load_watchlist():
    path = Path("watchlist.txt")
    if not path.exists():
        return {"keywords": [], "wallets": [], "handles": []}
    keywords, wallets, handles = [], [], []
    section = None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].lower()
        elif section == "keywords":
            keywords.append(line.lower())
        elif section == "wallets":
            wallets.append(line.lower())
        elif section == "handles":
            handles.append(line.lower().lstrip("@"))
    return {"keywords": keywords, "wallets": wallets, "handles": handles}

WATCHLIST = load_watchlist()

def load_seen_articles():
    """Load URLs of articles already sent in previous reports."""
    if SEEN_ARTICLES.exists():
        try:
            return set(json.loads(SEEN_ARTICLES.read_text()))
        except:
            return set()
    return set()

def save_seen_articles(urls):
    """Save seen article URLs — keep last 500 to avoid unbounded growth."""
    existing = load_seen_articles()
    all_urls = list(existing | urls)
    # Keep most recent 500
    all_urls = all_urls[-500:]
    SEEN_ARTICLES.write_text(json.dumps(all_urls, indent=2))

def check_watchlist(text):
    text_lower = text.lower()
    hits = []
    for kw in WATCHLIST["keywords"]:
        if kw in text_lower:
            hits.append(f"keyword:{kw}")
    for w in WATCHLIST["wallets"]:
        if w in text_lower:
            hits.append(f"wallet:{w}")
    return hits


# ════════════════════════════════════════════════════════════
# 1. RSS FEED MONITORING
# ════════════════════════════════════════════════════════════

def fetch_rss(feeds, keywords):
    raw = []
    for source, url in feeds.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                combined = (title + " " + summary).lower()
                matched = [kw for kw in keywords if kw.lower() in combined]
                if not matched:
                    continue
                priority = any(kw.lower() in combined for kw in HIGH_PRIORITY_KEYWORDS)
                wl = check_watchlist(title + " " + summary)

                # Better summary extraction — try multiple fields
                raw_summary = (
                    entry.get("summary") or
                    entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "" or
                    entry.get("description", "") or ""
                )
                clean = clean_text(raw_summary)[:250]
                if len(clean) < 20:
                    clean = f"[Full article at source — {source}]"

                raw.append({
                    "source":           source,
                    "title":            title,
                    "link":             entry.get("link", ""),
                    "published":        entry.get("published", ""),
                    "matched_keywords": matched,
                    "summary":          clean,
                    "priority":         priority or bool(wl),
                    "watchlist_hit":    wl,
                    "also_covered_by":  [],
                })
        except Exception as e:
            print(f"  RSS error [{source}]: {e}")
    deduped = deduplicate(raw)
    print(f"  RSS: {len(raw)} raw → {len(deduped)} unique")
    return deduped


# ════════════════════════════════════════════════════════════
# 2. POLYMARKET API — DIRECT TRADE SCRAPING
# ════════════════════════════════════════════════════════════

def fetch_polymarket_suspicious_trades():
    """
    Scrape Polymarket's public Gamma API for large trades on low-probability markets.
    No API key required. This is the core insider trading detection function.
    """
    flagged = []
    print("  Fetching Polymarket markets via Gamma API...")

    try:
        # Get active markets
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "active": "true",
            "closed": "false",
            "limit": 100,
            "order": "volume",
            "ascending": "false",
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)

        if resp.status_code != 200:
            print(f"  Polymarket API error: {resp.status_code}")
            return []

        markets = resp.json()
        print(f"  Got {len(markets)} active markets")

        for market in markets[:50]:  # Check top 50 by volume
            try:
                question   = market.get("question", "")
                market_id  = market.get("id", "")
                outcomes   = market.get("outcomes", "[]")
                prices     = market.get("outcomePrices", "[]")
                volume     = float(market.get("volume", 0) or 0)

                # Parse outcomes and prices
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                if isinstance(prices, str):
                    prices = json.loads(prices)

                # Check for low probability outcomes with high volume
                for i, (outcome, price) in enumerate(zip(outcomes, prices)):
                    try:
                        prob = float(price) * 100
                        if prob <= LOW_PROB_MAX_PCT and volume >= LARGE_TRADE_USD:
                            flagged.append({
                                "market_id":       market_id,
                                "question":        question,
                                "outcome":         outcome,
                                "probability_pct": round(prob, 1),
                                "volume_usd":      round(volume, 0),
                                "url":             f"https://polymarket.com/event/{market.get('slug', market_id)}",
                                "end_date":        market.get("endDate", ""),
                                "alert_reason":    f"High volume (${volume:,.0f}) on {prob:.1f}% probability outcome",
                            })
                    except (ValueError, TypeError):
                        continue

            except Exception as e:
                continue

    except Exception as e:
        print(f"  Polymarket API error: {e}")

    # Sort by volume descending, take top 10
    flagged = sorted(flagged, key=lambda x: x["volume_usd"], reverse=True)[:10]
    print(f"  Suspicious markets flagged: {len(flagged)}")
    return flagged


def fetch_polymarket_recent_large_trades():
    """
    Fetch recent large trades from Polymarket's CLOB data API.
    Flags individual trades over the threshold on low-probability markets.
    """
    flagged = []
    try:
        # CLOB trades endpoint
        url = "https://clob.polymarket.com/trades"
        params = {"limit": 500}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            trades = data if isinstance(data, list) else data.get("data", [])
            for trade in trades:
                size  = float(trade.get("size", 0) or 0)
                price = float(trade.get("price", 1) or 1)
                side  = trade.get("side", "")
                prob  = price * 100 if side == "BUY" else (1 - price) * 100

                if size >= LARGE_TRADE_USD and prob <= LOW_PROB_MAX_PCT:
                    maker = trade.get("maker_address", "unknown")
                    taker = trade.get("taker_address", "unknown")
                    flagged.append({
                        "maker":      maker,
                        "taker":      taker,
                        "size_usd":   round(size, 0),
                        "prob_pct":   round(prob, 1),
                        "side":       side,
                        "asset_id":   trade.get("asset_id", ""),
                        "timestamp":  trade.get("match_time", ""),
                        "wl_maker":   check_watchlist(maker),
                        "wl_taker":   check_watchlist(taker),
                    })

        flagged = sorted(flagged, key=lambda x: x["size_usd"], reverse=True)[:10]
    except Exception as e:
        print(f"  CLOB trades error: {e}")

    print(f"  Large individual trades flagged: {len(flagged)}")
    return flagged


# ════════════════════════════════════════════════════════════
# 3. WIN RATE TRACKER
# ════════════════════════════════════════════════════════════

WIN_RATE_FILE = Path("data/win_rate_tracker.json")

def load_win_rate():
    if WIN_RATE_FILE.exists():
        return json.loads(WIN_RATE_FILE.read_text())
    return {}

def save_win_rate(data):
    WIN_RATE_FILE.write_text(json.dumps(data, indent=2))

def log_suspicious_trade(wallet, market, prob_pct, amount_usd):
    data = load_win_rate()
    if wallet not in data:
        data[wallet] = {"trades": [], "wins": 0, "total": 0}
    data[wallet]["trades"].append({
        "date": TODAY, "market": market,
        "probability_pct": prob_pct, "amount_usd": amount_usd,
        "resolved": None, "won": None,
    })
    data[wallet]["total"] += 1
    save_win_rate(data)

def get_win_rate_alerts():
    data = load_win_rate()
    alerts = []
    for wallet, stats in data.items():
        resolved = [t for t in stats["trades"] if t["won"] is not None]
        if len(resolved) >= 3:
            wins = sum(1 for t in resolved if t["won"])
            rate = wins / len(resolved) * 100
            if rate >= WIN_RATE_ALERT:
                alerts.append({
                    "wallet": wallet, "win_rate_pct": round(rate, 1),
                    "total_trades": len(resolved), "wins": wins,
                })
    return alerts


# ════════════════════════════════════════════════════════════
# 4. UMA GOVERNANCE — STRICTER FILTERING
# ════════════════════════════════════════════════════════════

def fetch_uma_governance():
    alerts = []
    try:
        feed = feedparser.parse("https://discourse.uma.xyz/latest.rss")
        for entry in feed.entries[:30]:
            title   = entry.get("title", "")
            summary = entry.get("summary", "")
            combined = (title + " " + summary).lower()
            # MUCH stricter — must match one of the required keywords
            if any(kw in combined for kw in UMA_REQUIRED_KEYWORDS):
                alerts.append({
                    "title":     title,
                    "link":      entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary":   clean_text(summary)[:200],
                    "note":      "Review: check if dispute participant holds a position in this market.",
                })
    except Exception as e:
        print(f"  UMA error: {e}")
    print(f"  UMA alerts (filtered): {len(alerts)}")
    return alerts


# ════════════════════════════════════════════════════════════
# 5. OFAC — ONLY SHOW TRULY NEW ENTRIES (LAST 24H)
# ════════════════════════════════════════════════════════════

OFAC_CACHE    = Path("data/ofac_cache.json")
OFAC_SEEN     = Path("data/ofac_seen_uids.json")
SEEN_ARTICLES = Path("data/seen_articles.json")

def fetch_ofac_new():
    new_entries = []
    try:
        url  = "https://www.treasury.gov/ofac/downloads/sdn.xml"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        if resp.status_code != 200:
            return []

        soup    = BeautifulSoup(resp.text, "xml")
        current = {}
        for entry in soup.find_all("sdnEntry"):
            uid  = entry.find("uid")
            name = entry.find("lastName")
            if not uid or not name:
                continue
            for id_tag in entry.find_all("id"):
                id_type = id_tag.find("idType")
                id_num  = id_tag.find("idNumber")
                if id_type and id_num and "Digital" in (id_type.text or ""):
                    current[uid.text] = {"name": name.text, "wallet": id_num.text}

        # Load previously seen UIDs
        seen = set()
        if OFAC_SEEN.exists():
            seen = set(json.loads(OFAC_SEEN.read_text()))

        # Only report UIDs we haven't seen before
        for uid, entry in current.items():
            if uid not in seen:
                new_entries.append(entry)

        # Save updated seen set and cache
        OFAC_SEEN.write_text(json.dumps(list(current.keys()), indent=2))
        OFAC_CACHE.write_text(json.dumps(current, indent=2))

    except Exception as e:
        print(f"  OFAC error: {e}")

    # Cap at 10 — if there are more than 10 truly new ones summarize
    if len(new_entries) > 10:
        overflow = len(new_entries) - 10
        new_entries = new_entries[:10]
        new_entries.append({
            "name": f"+ {overflow} more new OFAC crypto additions",
            "wallet": "See data/ofac_cache.json for full list",
        })

    print(f"  New OFAC crypto additions: {len(new_entries)}")
    return new_entries


# ════════════════════════════════════════════════════════════
# 6. CONGRESSIONAL BILLS
# ════════════════════════════════════════════════════════════

def check_congress_bills(bills):
    updates = []
    if not CONGRESS_KEY:
        return updates
    for bill in bills:
        try:
            bt = "hr" if bill["id"].startswith("hr") else "s"
            bn = bill["id"].replace("hr","").replace("s","")
            url = f"https://api.congress.gov/v3/bill/{bill['congress']}/{bt}/{bn}"
            resp = requests.get(url, params={"api_key": CONGRESS_KEY}, timeout=10)
            if resp.status_code == 200:
                bd = resp.json().get("bill", {})
                updates.append({
                    "bill":          bill["name"],
                    "id":            bill["id"].upper(),
                    "latest_action": bd.get("latestAction",{}).get("text","No action found"),
                    "action_date":   bd.get("latestAction",{}).get("actionDate",""),
                    "url": f"https://www.congress.gov/bill/{bill['congress']}th-congress/{'house' if bt=='hr' else 'senate'}-bill/{bn}",
                })
        except Exception as e:
            print(f"  Bill error [{bill['name']}]: {e}")
    return updates


# ════════════════════════════════════════════════════════════
# 7. CASE INDEX
# ════════════════════════════════════════════════════════════

def update_case_index():
    case_files = sorted(Path("cases").glob("*.md"), reverse=True)
    case_files = [f for f in case_files if f.name != "INDEX.md"]
    lines = [f"# Investigation Case Index", f"_Updated: {TODAY}_ | **{len(case_files)} total cases**", "",
             "| Date | Case | File |", "|------|------|------|"]
    for f in case_files:
        try:
            first = f.read_text().split("\n")[0].lstrip("# ").strip()
        except:
            first = f.stem
        date_part = f.stem[:10] if len(f.stem) >= 10 else f.stem
        lines.append(f"| {date_part} | {first} | [{f.name}](cases/{f.name}) |")
    Path("cases/INDEX.md").write_text("\n".join(lines))
    print(f"  Case index: {len(case_files)} cases")


# ════════════════════════════════════════════════════════════
# 8. WEEKLY SUMMARY (Sundays)
# ════════════════════════════════════════════════════════════

def generate_weekly_summary():
    if WEEKDAY != 6:
        return None
    print("  Generating weekly summary...")
    week_hits, topic_freq, source_freq = [], {}, {}
    for i in range(7):
        date = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        p = Path(f"output/report_{date}.json")
        if p.exists():
            data = json.loads(p.read_text())
            for hit in data.get("alerts", []):
                week_hits.append(hit)
                for kw in hit.get("matched_keywords", []):
                    topic_freq[kw] = topic_freq.get(kw, 0) + 1
                source_freq[hit["source"]] = source_freq.get(hit["source"], 0) + 1
    top_topics  = sorted(topic_freq.items(),  key=lambda x: x[1], reverse=True)[:5]
    top_sources = sorted(source_freq.items(), key=lambda x: x[1], reverse=True)[:5]
    win_alerts  = get_win_rate_alerts()
    lines = [f"# Weekly Summary — {TODAY_PRETTY}", f"**{len(week_hits)} unique stories this week**", "",
             "## Top Topics", *[f"- {t}: {c} stories" for t, c in top_topics], "",
             "## Most Active Sources", *[f"- {s}: {c} stories" for s, c in top_sources]]
    if win_alerts:
        lines += ["", "## Win Rate Alerts"]
        for a in win_alerts:
            lines.append(f"- {a['wallet'][:16]}...: {a['win_rate_pct']}% win rate on {a['total_trades']} trades")
    path = Path(f"output/weekly_{TODAY}.md")
    path.write_text("\n".join(lines))
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 9. EMAIL BUILDER
# ════════════════════════════════════════════════════════════

def build_email(news, suspicious_markets, large_trades, uma, ofac, bills, win_alerts, weekly):
    high   = [h for h in news if h["priority"]]
    normal = [h for h in news if not h["priority"]]
    lines  = []

    lines += [f"POLYMARKET OSINT DAILY DIGEST — {TODAY_PRETTY}", "=" * 60, ""]

    # AT A GLANCE
    lines += ["AT A GLANCE", "-" * 40,
              f"Unique news stories:      {len(news)}",
              f"High priority:            {len(high)}",
              f"Suspicious markets:       {len(suspicious_markets)}",
              f"Large individual trades:  {len(large_trades)}",
              f"UMA governance alerts:    {len(uma)}",
              f"New OFAC crypto adds:     {len(ofac)}",
              f"Win rate alerts:          {len(win_alerts)}",
              f"Bills tracked:            {len(BILLS)}",
              ""]

    # SUSPICIOUS MARKETS (Polymarket API)
    if suspicious_markets:
        lines += ["SUSPICIOUS MARKET ACTIVITY — INVESTIGATE", "=" * 60]
        for m in suspicious_markets:
            lines += [
                f"\nMARKET: {m['question']}",
                f"  Outcome:       {m['outcome']}",
                f"  Probability:   {m['probability_pct']}%",
                f"  Volume:        ${m['volume_usd']:,.0f}",
                f"  Closes:        {m.get('end_date','unknown')}",
                f"  Flagged:       {TODAY} at time of report",
                f"  Alert:         {m['alert_reason']}",
                f"  URL:           {m['url']}",
                f"  ACTION:        High volume on low-probability outcome. Run OSINT on largest traders.",
            ]
        lines.append("")

    # LARGE INDIVIDUAL TRADES (CLOB API)
    if large_trades:
        lines += ["LARGE INDIVIDUAL TRADES — CLOB DATA", "=" * 60]
        for t in large_trades:
            wl_note = ""
            if t.get("wl_maker"):
                wl_note = f" *** WATCHLIST HIT: {', '.join(t['wl_maker'])}"
            if t.get("wl_taker"):
                wl_note += f" *** WATCHLIST HIT: {', '.join(t['wl_taker'])}"
            trade_time = t.get('timestamp','') or TODAY
            lines += [
                f"\nSize: ${t['size_usd']:,.0f} | Probability: {t['prob_pct']}% | Side: {t['side']}",
                f"  Time:     {trade_time}",
                f"  Maker:    {t['maker']}{wl_note}",
                f"  Taker:    {t['taker']}",
                f"  Asset:    {t['asset_id']}",
                f"  ACTION:   Run wallet OSINT. Check linked wallets and funding source.",
            ]
        lines.append("")

    # UMA GOVERNANCE
    if uma:
        lines += ["UMA GOVERNANCE / ORACLE DISPUTES", "=" * 60]
        for a in uma:
            uma_date = a.get('published','') or 'Date unknown'
            try:
                import email.utils
                parsed = email.utils.parsedate_to_datetime(uma_date)
                uma_date = parsed.strftime("%b %d, %Y")
            except: pass
            lines += [f"\n{a['title']}", f"  Published: {uma_date}", f"  {a['summary']}", f"  Link: {a['link']}", f"  NOTE: {a['note']}"]
        lines.append("")

    # OFAC — only truly new
    if ofac:
        lines += ["NEW OFAC CRYPTO SANCTIONS (LAST 24H) — CROSS-REFERENCE WITH POLYMARKET", "=" * 60]
        for o in ofac:
            lines += [f"\n{o['name']}", f"  Wallet: {o['wallet']}", f"  ACTION: Check against Polymarket trading history."]
        lines.append("")

    # WIN RATE ALERTS
    if win_alerts:
        lines += ["WIN RATE TRACKER ALERTS", "=" * 60]
        for a in win_alerts:
            lines += [f"\nWallet: {a['wallet']}", f"  Win rate: {a['win_rate_pct']}% on {a['total_trades']} tracked long-shot trades",
                      "  ACTION: Full OSINT investigation recommended."]
        lines.append("")

    # HIGH PRIORITY NEWS
    if high:
        lines += ["HIGH PRIORITY NEWS — READ THESE FIRST", "=" * 60]
        for i, item in enumerate(high, 1):
            lines.append(f"\n{i}. {item['title']}")
            lines.append(f"   Source:  {item['source']}  |  Published: {item.get('pub_date', 'Date unknown')}")
            if item.get("also_covered_by"):
                lines.append(f"   Also in: {', '.join(item['also_covered_by'])}")
            if item.get("watchlist_hit"):
                lines.append(f"   WATCHLIST: {', '.join(item['watchlist_hit'])}")
            lines.append(f"   TL;DR:   {item['summary']}")
            lines.append(f"   Link:    {item['link']}")
        lines.append("")

    # GENERAL NEWS
    if normal:
        lines += ["GENERAL NEWS & REGULATORY UPDATES", "=" * 60]
        for i, item in enumerate(normal, 1):
            lines.append(f"\n{i}. {item['title']}")
            lines.append(f"   Source:  {item['source']}  |  Published: {item.get('pub_date', 'Date unknown')}")
            if item.get("also_covered_by"):
                lines.append(f"   Also in: {', '.join(item['also_covered_by'])}")
            lines.append(f"   TL;DR:   {item['summary']}")
            lines.append(f"   Link:    {item['link']}")
        lines.append("")

    # BILLS
    lines += ["CONGRESSIONAL BILL TRACKER", "=" * 60]
    if bills:
        for b in bills:
            lines += [f"\n{b['bill']} ({b['id']})",
                      f"   Latest: {b['latest_action']}",
                      f"   Date:   {b.get('action_date','N/A')}",
                      f"   Link:   {b['url']}"]
    else:
        lines.append("Add CONGRESS_API_KEY to GitHub Secrets to enable bill tracking.")
    lines.append("")

    # WEEKLY
    if weekly:
        lines += ["WEEKLY SUMMARY", "=" * 60, weekly, ""]

    lines += ["=" * 60, f"Polymarket OSINT Monitor v5 — runs daily at 8 AM EST"]
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 10. SAVE + SEND
# ════════════════════════════════════════════════════════════

def save_report(news, suspicious_markets, large_trades, uma, ofac, bills, win_alerts, weekly):
    report = {
        "date": TODAY,
        "unique_news": len(news),
        "suspicious_markets": len(suspicious_markets),
        "large_trades": len(large_trades),
        "uma_alerts": len(uma),
        "ofac_new": len(ofac),
        "alerts": news,
        "suspicious_market_data": suspicious_markets,
        "large_trade_data": large_trades,
        "uma_governance": uma,
        "ofac_additions": ofac,
        "bill_updates": bills,
    }
    with open(f"output/report_{TODAY}.json", "w") as f:
        json.dump(report, f, indent=2)
    body = build_email(news, suspicious_markets, large_trades, uma, ofac, bills, win_alerts, weekly)
    with open(f"output/report_{TODAY}.md", "w") as f:
        f.write(body)
    
    # Save article URLs so they don't appear in future reports
    seen_urls = set(h.get("link","") for h in news if h.get("link",""))
    save_seen_articles(seen_urls)
    
    return body

def send_email(body, num_alerts):
    if not SMTP_PASSWORD:
        print("No SMTP password — skipping")
        return
    msg = MIMEMultipart()
    msg["Subject"] = f"Polymarket Digest {TODAY_PRETTY} — {num_alerts} stories"
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
    print(f"Polymarket OSINT Monitor v5 — {TODAY}")
    print("1. RSS feeds...")
    news = fetch_rss(RSS_FEEDS, KEYWORDS)
    print("2. Polymarket suspicious markets (Gamma API)...")
    suspicious_markets = fetch_polymarket_suspicious_trades()
    print("3. Large individual trades (CLOB API)...")
    large_trades = fetch_polymarket_recent_large_trades()
    print("4. UMA governance (filtered)...")
    uma = fetch_uma_governance()
    print("5. OFAC new additions only...")
    ofac = fetch_ofac_new()
    print("6. Congressional bills...")
    bills = check_congress_bills(BILLS)
    print("7. Win rate alerts...")
    win_alerts = get_win_rate_alerts()
    print("8. Case index...")
    update_case_index()
    print("9. Weekly summary check...")
    weekly = generate_weekly_summary()
    print("10. Saving and sending...")
    body = save_report(news, suspicious_markets, large_trades, uma, ofac, bills, win_alerts, weekly)
    send_email(body, len(news))
    print(f"Done. {len(news)} stories | {len(suspicious_markets)} suspicious markets | {len(large_trades)} large trades")

if __name__ == "__main__":
    main()
