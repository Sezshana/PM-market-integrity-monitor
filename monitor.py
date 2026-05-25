"""
Polymarket OSINT Monitor v8
Full suite with: narrative summary, smart subject lines,
quiet day mode, priority scoring, weekly story threading,
cross-day deduplication, dates everywhere.
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
import email.utils

# HTML email template
from email_template import build_html_email

# On-chain monitoring via Polygonscan/Etherscan
POLYGONSCAN_KEY = os.environ.get("POLYGONSCAN_KEY", "")
POLYMARKET_CTF  = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # Main CTF Exchange on Polygon
USDC_POLYGON    = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
ETHERSCAN_POLY  = "https://api.etherscan.io/v2/api"

ALERT_EMAIL   = os.environ.get("ALERT_EMAIL", "shanabautista0819@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
CONGRESS_KEY  = os.environ.get("CONGRESS_API_KEY", "")
DUNE_API_KEY  = os.environ.get("DUNE_API_KEY", "")

TODAY        = datetime.date.today().isoformat()
TODAY_PRETTY = datetime.date.today().strftime("%B %d, %Y")
WEEKDAY      = datetime.date.today().weekday()

for folder in ["output", "cases", "data"]:
    Path(folder).mkdir(exist_ok=True)

# ── DATA FILES ───────────────────────────────────────────────
SEEN_ARTICLES = Path("data/seen_articles.json")
OFAC_CACHE    = Path("data/ofac_cache.json")
OFAC_SEEN     = Path("data/ofac_seen_uids.json")
WIN_RATE_FILE = Path("data/win_rate_tracker.json")
STORY_THREADS = Path("data/story_threads.json")

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

# Priority keywords with weights — more matches = higher score
PRIORITY_WEIGHTS = {
    "polymarket": 3,
    "kalshi": 2,
    "insider trading prediction": 5,
    "prediction market manipulation": 5,
    "CFTC enforcement": 4,
    "oracle manipulation": 4,
    "UMA protocol": 3,
    "wash trading": 3,
    "exploit": 3,
    "insider trading": 4,
    "congressional": 2,
    "probe": 2,
    "investigation": 2,
    "sanctions": 2,
    "OFAC": 3,
    "arrest": 4,
    "indictment": 5,
    "lawsuit": 3,
    "fine": 3,
    "penalty": 3,
    "ban": 2,
}

UMA_REQUIRED = [
    "polymarket", "dispute", "resolution", "incorrect", "manipulat",
    "bad faith", "exploit", "governance attack", "slashing", "bad-faith"
]

BILLS = [
    {"name": "PREDICT Act",                                   "id": "hr8076", "congress": "119"},
    {"name": "End Prediction Market Corruption Act",          "id": "s4017",  "congress": "119"},
    {"name": "Prediction Markets Security and Integrity Act", "id": "s4060",  "congress": "119"},
    {"name": "Public Integrity in Financial Prediction Markets Act","id":"s4188","congress":"119"},
    {"name": "STOP Corrupt Bets Act",                        "id": "s4226",  "congress": "119"},
    {"name": "BETS OFF Act",                                  "id": "s4115",  "congress": "119"},
    {"name": "Event Contract Enforcement Act",                "id": "hr7840", "congress": "119"},
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

def parse_date(raw_date):
    """Parse RSS date string into human-readable format."""
    try:
        parsed = email.utils.parsedate_to_datetime(raw_date)
        return parsed.strftime("%b %d, %Y")
    except:
        return raw_date[:10] if raw_date and len(raw_date) >= 10 else "Date unknown"

def score_article(title, summary, matched_keywords):
    """Score an article by priority — higher = more important."""
    combined = (title + " " + summary).lower()
    score = 0
    for kw, weight in PRIORITY_WEIGHTS.items():
        if kw.lower() in combined:
            score += weight
    return score

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


# ════════════════════════════════════════════════════════════
# SEEN ARTICLES (cross-day deduplication)
# ════════════════════════════════════════════════════════════

def load_seen_articles():
    if SEEN_ARTICLES.exists():
        try:
            return set(json.loads(SEEN_ARTICLES.read_text()))
        except:
            return set()
    return set()

def save_seen_articles(urls):
    existing = load_seen_articles()
    all_urls = list(existing | urls)
    all_urls = all_urls[-500:]
    SEEN_ARTICLES.write_text(json.dumps(all_urls, indent=2))


# ════════════════════════════════════════════════════════════
# STORY THREADS (weekly pattern tracking)
# ════════════════════════════════════════════════════════════

def load_story_threads():
    if STORY_THREADS.exists():
        try:
            return json.loads(STORY_THREADS.read_text())
        except:
            return {}
    return {}

def save_story_threads(threads):
    STORY_THREADS.write_text(json.dumps(threads, indent=2))

def update_story_threads(news_hits):
    """
    Track developing stories across days.
    Groups articles by topic fingerprint and records which days they appeared.
    """
    threads = load_story_threads()
    cutoff  = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()

    # Remove threads older than 14 days
    threads = {k: v for k, v in threads.items()
               if v.get("last_seen", "") >= cutoff}

    for hit in news_hits:
        fp = title_fingerprint(hit["title"])
        if not fp:
            continue
        # Find matching thread
        matched_key = None
        for key, thread in threads.items():
            if stories_are_similar(hit["title"], thread["representative_title"]):
                matched_key = key
                break
        if matched_key:
            thread = threads[matched_key]
            if TODAY not in thread["dates_seen"]:
                thread["dates_seen"].append(TODAY)
            thread["last_seen"] = TODAY
            thread["mention_count"] = len(thread["dates_seen"])
        else:
            threads[fp] = {
                "representative_title": hit["title"],
                "dates_seen":           [TODAY],
                "last_seen":            TODAY,
                "mention_count":        1,
            }

    save_story_threads(threads)

    # Return threads that have appeared on 2+ days — these are developing stories
    developing = [
        v for v in threads.values()
        if v["mention_count"] >= 2 and v["last_seen"] == TODAY
    ]
    return sorted(developing, key=lambda x: x["mention_count"], reverse=True)


# ════════════════════════════════════════════════════════════
# WATCHLIST
# ════════════════════════════════════════════════════════════

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
# RSS FEEDS
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

                wl      = check_watchlist(title + " " + summary)
                score   = score_article(title, summary, matched)
                pub_date = parse_date(entry.get("published", ""))

                clean = clean_text(entry.get("summary",""))[:250]
                if len(clean) < 20:
                    clean = f"[See full article at {source}]"

                raw.append({
                    "source":           source,
                    "title":            title,
                    "link":             entry.get("link", ""),
                    "published":        entry.get("published", ""),
                    "pub_date":         pub_date,
                    "matched_keywords": matched,
                    "summary":          clean,
                    "score":            score,
                    "priority":         score >= 3 or bool(wl),
                    "watchlist_hit":    wl,
                    "also_covered_by":  [],
                })
        except Exception as e:
            print(f"  RSS error [{source}]: {e}")

    deduped = deduplicate(raw)

    # Cross-day deduplication — skip articles already sent
    seen = load_seen_articles()
    fresh = [h for h in deduped if h.get("link","") not in seen]

    # Sort by score descending so most important comes first
    fresh = sorted(fresh, key=lambda x: x["score"], reverse=True)

    print(f"  RSS: {len(raw)} raw -> {len(deduped)} unique -> {len(fresh)} new today")
    return fresh


# ════════════════════════════════════════════════════════════
# POLYMARKET API — TRADE SCRAPING
# ════════════════════════════════════════════════════════════

def fetch_polymarket_suspicious_trades():
    flagged = []
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {"active":"true","closed":"false","limit":100,"order":"volume","ascending":"false"}
        resp = requests.get(url, params=params, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        if resp.status_code != 200:
            return []
        markets = resp.json()
        for market in markets[:50]:
            question  = market.get("question","")
            market_id = market.get("id","")
            outcomes  = market.get("outcomes","[]")
            prices    = market.get("outcomePrices","[]")
            volume    = float(market.get("volume",0) or 0)
            if isinstance(outcomes, str): outcomes = json.loads(outcomes)
            if isinstance(prices, str):   prices   = json.loads(prices)
            # Skip markets that have already closed
            end_date_raw = market.get("endDate","")
            if end_date_raw:
                try:
                    end_date_parsed = datetime.date.fromisoformat(end_date_raw[:10])
                    if end_date_parsed < datetime.date.today():
                        continue  # Market already closed — skip
                except: pass

            for outcome, price in zip(outcomes, prices):
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
                            "end_date":        end_date_raw[:10] if end_date_raw else "unknown",
                            "flagged_date":    TODAY,
                            "alert_reason":    f"${volume:,.0f} volume on {prob:.1f}% probability outcome",
                        })
                except: continue
    except Exception as e:
        print(f"  Polymarket API error: {e}")
    flagged = sorted(flagged, key=lambda x: x["volume_usd"], reverse=True)[:10]
    print(f"  Suspicious markets: {len(flagged)}")
    return flagged


def fetch_polymarket_recent_large_trades():
    flagged = []
    try:
        resp = requests.get("https://clob.polymarket.com/trades",
                           params={"limit":500},
                           headers={"User-Agent":"Mozilla/5.0"},
                           timeout=15)
        if resp.status_code == 200:
            data   = resp.json()
            trades = data if isinstance(data, list) else data.get("data", [])
            for trade in trades:
                size  = float(trade.get("size",0) or 0)
                price = float(trade.get("price",1) or 1)
                side  = trade.get("side","")
                prob  = price * 100 if side == "BUY" else (1 - price) * 100
                if size >= LARGE_TRADE_USD and prob <= LOW_PROB_MAX_PCT:
                    maker = trade.get("maker_address","unknown")
                    taker = trade.get("taker_address","unknown")
                    ts    = trade.get("match_time","") or TODAY
                    flagged.append({
                        "maker":     maker,
                        "taker":     taker,
                        "size_usd":  round(size, 0),
                        "prob_pct":  round(prob, 1),
                        "side":      side,
                        "asset_id":  trade.get("asset_id",""),
                        "timestamp": ts[:10] if len(str(ts)) >= 10 else ts,
                        "wl_maker":  check_watchlist(maker),
                        "wl_taker":  check_watchlist(taker),
                    })
        flagged = sorted(flagged, key=lambda x: x["size_usd"], reverse=True)[:10]
    except Exception as e:
        print(f"  CLOB error: {e}")
    print(f"  Large trades: {len(flagged)}")
    return flagged


# ════════════════════════════════════════════════════════════
# WIN RATE TRACKER
# ════════════════════════════════════════════════════════════

def load_win_rate():
    if WIN_RATE_FILE.exists():
        return json.loads(WIN_RATE_FILE.read_text())
    return {}

def save_win_rate(data):
    WIN_RATE_FILE.write_text(json.dumps(data, indent=2))

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
                    "wallet":       wallet,
                    "win_rate_pct": round(rate, 1),
                    "total_trades": len(resolved),
                    "wins":         wins,
                })
    return alerts


# ════════════════════════════════════════════════════════════
# UMA GOVERNANCE
# ════════════════════════════════════════════════════════════

def fetch_uma_governance():
    alerts = []
    try:
        feed = feedparser.parse("https://discourse.uma.xyz/latest.rss")
        for entry in feed.entries[:30]:
            title   = entry.get("title","")
            summary = entry.get("summary","")
            combined = (title + " " + summary).lower()
            if any(kw in combined for kw in UMA_REQUIRED):
                alerts.append({
                    "title":     title,
                    "link":      entry.get("link",""),
                    "published": parse_date(entry.get("published","")),
                    "summary":   clean_text(summary)[:200],
                    "note":      "Review: check if dispute participant holds a position in this market.",
                })
    except Exception as e:
        print(f"  UMA error: {e}")
    print(f"  UMA alerts: {len(alerts)}")
    return alerts


# ════════════════════════════════════════════════════════════
# OFAC
# ════════════════════════════════════════════════════════════

def fetch_ofac_new():
    new_entries = []
    try:
        resp = requests.get("https://www.treasury.gov/ofac/downloads/sdn.xml",
                           headers={"User-Agent":"Mozilla/5.0"}, timeout=20)
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
        seen = set()
        if OFAC_SEEN.exists():
            seen = set(json.loads(OFAC_SEEN.read_text()))
        for uid, entry in current.items():
            if uid not in seen:
                new_entries.append(entry)
        OFAC_SEEN.write_text(json.dumps(list(current.keys()), indent=2))
        OFAC_CACHE.write_text(json.dumps(current, indent=2))
    except Exception as e:
        print(f"  OFAC error: {e}")
    if len(new_entries) > 10:
        overflow = len(new_entries) - 10
        new_entries = new_entries[:10]
        new_entries.append({"name": f"+ {overflow} more", "wallet": "See data/ofac_cache.json"})
    print(f"  New OFAC additions: {len(new_entries)}")
    return new_entries


# ════════════════════════════════════════════════════════════
# CONGRESSIONAL BILLS
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
                bd = resp.json().get("bill",{})
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
# NARRATIVE SUMMARY
# ════════════════════════════════════════════════════════════

def build_narrative_summary(news, suspicious_markets, large_trades, uma, ofac, developing_stories):
    """
    Build a 3-5 sentence human-readable summary of the day's intelligence.
    This goes at the very top of the email so you know in 10 seconds what happened today.
    """
    parts = []
    high  = [h for h in news if h["priority"]]

    # Top story
    if high:
        top = high[0]
        parts.append(f"Today's top story: {top['title']} (via {top['source']}, {top['pub_date']}).")
        if len(high) > 1:
            parts.append(f"There are {len(high)} high priority alerts total today.")
    elif news:
        parts.append(f"No high priority alerts today. {len(news)} general news stories were collected.")
    else:
        parts.append("No new news articles today — all recent stories have already been sent.")

    # Trade activity
    if suspicious_markets or large_trades:
        trade_msg = []
        if suspicious_markets:
            top_market = suspicious_markets[0]
            trade_msg.append(f"One suspicious market flagged: '{top_market['question']}' with ${top_market['volume_usd']:,.0f} in volume at {top_market['probability_pct']}% probability")
        if large_trades:
            trade_msg.append(f"{len(large_trades)} large individual trade(s) detected on low-probability markets")
        parts.append(". ".join(trade_msg) + ".")
    else:
        parts.append("No suspicious trading activity detected today.")

    # Developing stories
    if developing_stories:
        top_dev = developing_stories[0]
        days = len(top_dev["dates_seen"])
        parts.append(f"Developing story to watch: '{top_dev['representative_title'][:80]}...' has appeared for {days} consecutive days.")

    # UMA / regulatory
    if uma:
        parts.append(f"{len(uma)} UMA governance dispute(s) flagged — check the UMA tab for details.")
    if ofac:
        parts.append(f"{len(ofac)} new OFAC crypto sanctions added — cross-reference with Polymarket trading history.")

    return " ".join(parts)


# ════════════════════════════════════════════════════════════
# SMART SUBJECT LINE
# ════════════════════════════════════════════════════════════

def build_subject(news, suspicious_markets, large_trades, is_quiet):
    if is_quiet:
        return f"Polymarket Digest {TODAY_PRETTY} — Quiet day, no major alerts"

    high = [h for h in news if h["priority"]]

    if suspicious_markets and high:
        top_market  = suspicious_markets[0]
        top_article = high[0]["title"][:50]
        return f"Polymarket Digest {TODAY_PRETTY} — {top_article}... + suspicious trade flagged"
    elif suspicious_markets:
        top = suspicious_markets[0]
        return f"Polymarket Digest {TODAY_PRETTY} — Suspicious trade: ${top['volume_usd']:,.0f} on {top['probability_pct']}% market"
    elif high:
        top = high[0]["title"][:60]
        count = len(high)
        return f"Polymarket Digest {TODAY_PRETTY} — {top}{'...' if len(top)==60 else ''} [{count} alerts]"
    else:
        return f"Polymarket Digest {TODAY_PRETTY} — {len(news)} stories"


# ════════════════════════════════════════════════════════════
# CASE INDEX
# ════════════════════════════════════════════════════════════

def update_case_index():
    case_files = sorted([f for f in Path("cases").glob("*.md") if f.name != "INDEX.md"], reverse=True)
    lines = [f"# Investigation Case Index", f"_Updated: {TODAY}_ | **{len(case_files)} total cases**", "",
             "| Date | Case | File |", "|------|------|------|"]
    for f in case_files:
        try:
            first = f.read_text().split("\n")[0].lstrip("# ").strip()
        except:
            first = f.stem
        lines.append(f"| {f.stem[:10]} | {first} | [{f.name}](cases/{f.name}) |")
    Path("cases/INDEX.md").write_text("\n".join(lines))


# ════════════════════════════════════════════════════════════
# WEEKLY SUMMARY (Sundays)
# ════════════════════════════════════════════════════════════

def generate_weekly_summary(developing_stories):
    if WEEKDAY != 6:
        return None
    print("  Generating weekly summary...")
    week_hits, topic_freq, source_freq = [], {}, {}
    for i in range(7):
        date = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        p = Path(f"output/report_{date}.json")
        if p.exists():
            try:
                data = json.loads(p.read_text())
                for hit in data.get("alerts",[]):
                    week_hits.append(hit)
                    for kw in hit.get("matched_keywords",[]):
                        topic_freq[kw] = topic_freq.get(kw,0) + 1
                    source_freq[hit["source"]] = source_freq.get(hit["source"],0) + 1
            except: pass

    top_topics  = sorted(topic_freq.items(),  key=lambda x: x[1], reverse=True)[:5]
    top_sources = sorted(source_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    lines = [
        f"WEEKLY INTELLIGENCE SUMMARY — Week ending {TODAY_PRETTY}",
        f"Total unique stories this week: {len(week_hits)}",
        "",
        "TOP TOPICS THIS WEEK:",
        *[f"  {t}: {c} stories" for t,c in top_topics],
        "",
        "MOST ACTIVE SOURCES:",
        *[f"  {s}: {c} stories" for s,c in top_sources],
    ]

    if developing_stories:
        lines += ["", "DEVELOPING STORIES (appeared on multiple days this week):"]
        for story in developing_stories[:5]:
            lines.append(f"  [{story['mention_count']} days] {story['representative_title'][:80]}")

    win_alerts = get_win_rate_alerts()
    if win_alerts:
        lines += ["", "WIN RATE TRACKER ALERTS:"]
        for a in win_alerts:
            lines.append(f"  {a['wallet'][:20]}...: {a['win_rate_pct']}% win rate on {a['total_trades']} trades")

    path = Path(f"output/weekly_{TODAY}.md")
    path.write_text("\n".join(lines))
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# EMAIL BUILDER
# ════════════════════════════════════════════════════════════

def build_email(news, suspicious_markets, large_trades, onchain_txs, uma, ofac,
                bills, win_alerts, weekly, narrative, developing_stories):
    high   = [h for h in news if h["priority"]]
    normal = [h for h in news if not h["priority"]]

    is_quiet = (len(high) == 0 and len(suspicious_markets) == 0
                and len(large_trades) == 0 and len(uma) == 0)

    lines = []
    lines += [f"POLYMARKET OSINT DAILY DIGEST — {TODAY_PRETTY}", "=" * 60, ""]

    # NARRATIVE SUMMARY — top of email
    lines += ["TODAY'S INTELLIGENCE SUMMARY", "-" * 40, narrative, ""]

    # AT A GLANCE
    lines += ["AT A GLANCE", "-" * 40,
              f"High priority alerts:     {len(high)}",
              f"Total news stories:       {len(news)}",
              f"Suspicious markets:       {len(suspicious_markets)}",
              f"Large individual trades:  {len(large_trades)}",
              f"UMA governance alerts:    {len(uma)}",
              f"New OFAC additions:       {len(ofac)}",
              f"Win rate alerts:          {len(win_alerts)}",
              f"Bills tracked:            {len(bills)}",
              f"Report generated:         {TODAY} | Cleveland EDT = UTC-4",
              ""]

    # QUIET DAY — short version
    if is_quiet:
        lines += [
            "QUIET DAY",
            "-" * 40,
            "No high priority news, suspicious trades, or governance disputes today.",
            "Congressional bill status and general news below.",
            "",
        ]

    # DEVELOPING STORIES
    if developing_stories:
        lines += ["DEVELOPING STORIES — WATCH THESE", "=" * 60]
        for story in developing_stories[:3]:
            days = len(story["dates_seen"])
            lines += [
                f"\n[DAY {days}] {story['representative_title'][:80]}",
                f"  Active since: {story['dates_seen'][0]}  |  Last seen: {story['last_seen']}",
                f"  This story has appeared in {days} daily reports — likely an ongoing development.",
            ]
        lines.append("")

    # SUSPICIOUS MARKETS
    if suspicious_markets:
        lines += ["SUSPICIOUS MARKET ACTIVITY — INVESTIGATE", "=" * 60]
        for m in suspicious_markets:
            lines += [
                f"\nMARKET: {m['question']}",
                f"  Outcome:       {m['outcome']}",
                f"  Probability:   {m['probability_pct']}%",
                f"  Volume:        ${m['volume_usd']:,.0f}",
                f"  Market closes: {m.get('end_date','unknown')}",
                f"  Flagged:       {m['flagged_date']}",
                f"  Alert:         {m['alert_reason']}",
                f"  URL:           {m['url']}",
                f"  ACTION:        High volume on low-probability outcome. Run OSINT on largest traders.",
            ]
        lines.append("")

    # ON-CHAIN LARGE TRANSACTIONS

    # ON-CHAIN LARGE TRANSACTIONS
    if onchain_txs:
        lines += ["ON-CHAIN LARGE TRANSACTIONS (POLYGON)", "=" * 60]
        lines.append("Direct Polymarket contract transactions over $10,000 USDC in last 24 hours.")
        for tx in onchain_txs:
            wl_note = f" *** WATCHLIST HIT" if tx.get("watchlist") else ""
            lines += [
                f"\n${tx['value_usdc']:,.2f} USDC  |  {tx['timestamp']}",
                f"  From:    {tx['from']}{wl_note}",
                f"  To:      {tx['to']}",
                f"  TX:      {tx['polygonscan']}",
                f"  Wallet:  {tx['from_link']}",
                f"  ACTION:  Check wallet age, funding source, and Polymarket position history.",
            ]
        lines.append("")

    # LARGE TRADES
    if large_trades:
        lines += ["LARGE INDIVIDUAL TRADES — CLOB DATA", "=" * 60]
        for t in large_trades:
            wl_note = ""
            if t.get("wl_maker"): wl_note += f" *** WATCHLIST: {', '.join(t['wl_maker'])}"
            if t.get("wl_taker"): wl_note += f" *** WATCHLIST: {', '.join(t['wl_taker'])}"
            lines += [
                f"\n${t['size_usd']:,.0f} | {t['prob_pct']}% probability | Side: {t['side']}",
                f"  Date:   {t['timestamp']}",
                f"  Maker:  {t['maker']}{wl_note}",
                f"  Taker:  {t['taker']}",
                f"  Asset:  {t['asset_id']}",
                f"  ACTION: Run wallet OSINT. Trace funding source. Check win rate tracker.",
            ]
        lines.append("")

    # UMA GOVERNANCE
    if uma:
        lines += ["UMA GOVERNANCE / ORACLE DISPUTES", "=" * 60]
        for a in uma:
            lines += [f"\n{a['title']}", f"  Published: {a['published']}",
                      f"  {a['summary']}", f"  Link: {a['link']}", f"  NOTE: {a['note']}"]
        lines.append("")

    # OFAC
    if ofac:
        lines += ["NEW OFAC CRYPTO SANCTIONS — CROSS-REFERENCE WITH POLYMARKET", "=" * 60]
        for o in ofac:
            lines += [f"\n{o['name']}", f"  Wallet: {o['wallet']}",
                      f"  ACTION: Check this wallet against Polymarket trading history."]
        lines.append("")

    # WIN RATE ALERTS
    if win_alerts:
        lines += ["WIN RATE TRACKER ALERTS", "=" * 60]
        for a in win_alerts:
            lines += [f"\nWallet: {a['wallet']}",
                      f"  Win rate: {a['win_rate_pct']}% on {a['total_trades']} tracked long-shot trades",
                      f"  ACTION: Full OSINT investigation recommended."]
        lines.append("")

    # HIGH PRIORITY NEWS
    if high:
        lines += ["HIGH PRIORITY NEWS — READ THESE FIRST", "=" * 60]
        for i, item in enumerate(high, 1):
            lines.append(f"\n{i}. {item['title']}")
            lines.append(f"   Source:    {item['source']}  |  Published: {item['pub_date']}")
            lines.append(f"   Priority:  Score {item['score']} — {', '.join(item['matched_keywords'][:3])}")
            if item.get("also_covered_by"):
                lines.append(f"   Also in:   {', '.join(item['also_covered_by'])}")
            if item.get("watchlist_hit"):
                lines.append(f"   WATCHLIST: {', '.join(item['watchlist_hit'])}")
            lines.append(f"   TL;DR:     {item['summary']}")
            lines.append(f"   Link:      {item['link']}")
        lines.append("")

    # GENERAL NEWS
    if normal:
        lines += ["GENERAL NEWS & REGULATORY UPDATES", "=" * 60]
        for i, item in enumerate(normal, 1):
            lines.append(f"\n{i}. {item['title']}")
            lines.append(f"   Source:  {item['source']}  |  Published: {item['pub_date']}")
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
        lines += ["", "WEEKLY SUMMARY", "=" * 60, weekly, ""]

    lines += ["=" * 60, f"Polymarket OSINT Monitor v8 — runs daily at 7 AM EDT"]
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# SAVE + SEND
# ════════════════════════════════════════════════════════════

def save_report(news, suspicious_markets, large_trades, onchain_txs, uma, ofac,
                bills, win_alerts, weekly, narrative, developing_stories):
    report = {
        "date":                TODAY,
        "unique_news":         len(news),
        "suspicious_markets":  len(suspicious_markets),
        "large_trades":        len(large_trades),
        "uma_alerts":          len(uma),
        "ofac_new":            len(ofac),
        "alerts":              news,
        "suspicious_market_data": suspicious_markets,
        "large_trade_data":    large_trades,
        "onchain_txs":         onchain_txs,
        "uma_governance":      uma,
        "ofac_additions":      ofac,
        "bill_updates":        bills,
        "developing_stories":  developing_stories,
        "narrative":           narrative,
    }
    with open(f"output/report_{TODAY}.json","w") as f:
        json.dump(report, f, indent=2)

    is_quiet = (len([h for h in news if h["priority"]]) == 0
                and len(suspicious_markets) == 0
                and len(large_trades) == 0
                and len(uma) == 0)

    body    = build_email(news, suspicious_markets, large_trades, onchain_txs, uma, ofac,
                         bills, win_alerts, weekly, narrative, developing_stories)
    subject = build_subject(news, suspicious_markets, large_trades, is_quiet)

    with open(f"output/report_{TODAY}.md","w") as f:
        f.write(body)

    # Build HTML version
    body_html = build_html_email(
        news, suspicious_markets, large_trades, onchain_txs,
        uma, ofac, bills, win_alerts, weekly,
        narrative, developing_stories, TODAY_PRETTY
    )

    # Save seen articles
    seen_urls = set(h.get("link","") for h in news if h.get("link",""))
    save_seen_articles(seen_urls)

    return body, body_html, subject


def send_email(body_plain, body_html, subject):
    if not SMTP_PASSWORD:
        print("No SMTP password — skipping email")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = ALERT_EMAIL
    msg["To"]      = ALERT_EMAIL
    # Plain text fallback first, HTML preferred
    msg.attach(MIMEText(body_plain, "plain"))
    msg.attach(MIMEText(body_html,  "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ALERT_EMAIL, SMTP_PASSWORD)
            server.sendmail(ALERT_EMAIL, ALERT_EMAIL, msg.as_string())
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email error: {e}")


# ════════════════════════════════════════════════════════════
# ON-CHAIN MONITORING (Polygonscan/Etherscan)
# ════════════════════════════════════════════════════════════

def fetch_onchain_large_txs():
    """
    Scan Polymarket's CTF Exchange contract for large USDC transactions
    in the last 24 hours using Etherscan's Polygon API.
    """
    if not POLYGONSCAN_KEY:
        print("  On-chain: no POLYGONSCAN_KEY set — skipping")
        return []

    flagged = []
    yesterday_ts = int((datetime.datetime.now() - datetime.timedelta(days=1)).timestamp())

    try:
        resp = requests.get(ETHERSCAN_POLY, params={
            "chainid":         137,
            "module":          "account",
            "action":          "tokentx",
            "contractaddress": USDC_POLYGON,
            "address":         POLYMARKET_CTF,
            "sort":            "desc",
            "apikey":          POLYGONSCAN_KEY,
            "offset":          200,
            "page":            1,
        }, timeout=15)

        data = resp.json()
        if data.get("status") != "1":
            print(f"  On-chain API response: {data.get('message','unknown error')}")
            return []

        for tx in data.get("result", []):
            ts    = int(tx.get("timeStamp", 0))
            if ts < yesterday_ts:
                continue
            value = int(tx.get("value", 0)) / 1e6  # USDC 6 decimals
            if value < LARGE_TRADE_USD:
                continue

            from_addr = tx.get("from","")
            to_addr   = tx.get("to","")
            tx_date   = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")
            wl        = check_watchlist(from_addr + " " + to_addr)

            flagged.append({
                "from":        from_addr,
                "to":          to_addr,
                "value_usdc":  round(value, 2),
                "tx_hash":     tx.get("hash",""),
                "timestamp":   tx_date,
                "polygonscan": f"https://polygonscan.com/tx/{tx.get('hash','')}",
                "from_link":   f"https://polygonscan.com/address/{from_addr}",
                "watchlist":   wl,
            })

    except Exception as e:
        print(f"  On-chain error: {e}")

    flagged = sorted(flagged, key=lambda x: x["value_usdc"], reverse=True)[:10]
    print(f"  On-chain large USDC transactions: {len(flagged)}")
    return flagged


def get_wallet_age(address):
    """Check when a wallet first appeared on Polygon."""
    if not POLYGONSCAN_KEY:
        return None
    try:
        resp = requests.get(ETHERSCAN_POLY, params={
            "chainid": 137,
            "module":  "account",
            "action":  "txlist",
            "address": address,
            "startblock": 0,
            "sort":    "asc",
            "apikey":  POLYGONSCAN_KEY,
            "offset":  1,
            "page":    1,
        }, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            ts = int(data["result"][0].get("timeStamp", 0))
            if ts:
                return datetime.datetime.fromtimestamp(ts).date().isoformat()
    except: pass
    return None


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def main():
    print(f"Polymarket OSINT Monitor v8 — {TODAY}")

    print("1. RSS feeds (with cross-day deduplication and priority scoring)...")
    news = fetch_rss(RSS_FEEDS, KEYWORDS)

    print("2. Story thread tracking...")
    developing_stories = update_story_threads(news)
    print(f"   Developing stories: {len(developing_stories)}")

    print("3. Polymarket suspicious markets...")
    suspicious_markets = fetch_polymarket_suspicious_trades()

    print("3b. On-chain large transactions (Polygonscan)...")
    onchain_txs = fetch_onchain_large_txs()

    print("4. Large individual trades...")
    large_trades = fetch_polymarket_recent_large_trades()

    print("5. UMA governance...")
    uma = fetch_uma_governance()

    print("6. OFAC new additions...")
    ofac = fetch_ofac_new()

    print("7. Congressional bills...")
    bills = check_congress_bills(BILLS)

    print("8. Win rate alerts...")
    win_alerts = get_win_rate_alerts()

    print("9. Case index...")
    update_case_index()

    print("10. Weekly summary check...")
    weekly = generate_weekly_summary(developing_stories)

    print("11. Building narrative summary...")
    narrative = build_narrative_summary(news, suspicious_markets, large_trades, uma, ofac, developing_stories)

    print("12. Saving report and sending email...")
    body, body_html, subject = save_report(news, suspicious_markets, large_trades, onchain_txs, uma, ofac,
                                bills, win_alerts, weekly, narrative, developing_stories)
    send_email(body, body_html, subject)

    high = len([h for h in news if h["priority"]])
    print(f"On-chain txs: {len(onchain_txs)}")
    print(f"Done. {len(news)} new stories ({high} high priority) | {len(suspicious_markets)} suspicious markets | subject: {subject}")


if __name__ == "__main__":
    main()
