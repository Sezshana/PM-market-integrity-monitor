"""RSS collection, scoring, deduplication, and watchlist helpers."""

from __future__ import annotations

import datetime
import email.utils
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
import feedparser

from polymarket_monitor import config
from polymarket_monitor.storage.json_store import (
    load_seen_articles,
    load_story_threads,
    save_seen_articles as persist_seen_articles,
    save_story_threads,
)


def clean_text(html: str) -> str:
    text = BeautifulSoup(html or "", "html.parser").get_text()
    return " ".join(text.split())


def parse_date(raw_date: str) -> str:
    try:
        parsed = email.utils.parsedate_to_datetime(raw_date)
        return parsed.strftime("%b %d, %Y")
    except Exception:
        return raw_date[:10] if raw_date and len(raw_date) >= 10 else "Date unknown"


def score_article(title: str, summary: str, matched_keywords: list[str]) -> int:
    combined = (title + " " + summary).lower()
    return sum(weight for kw, weight in config.PRIORITY_WEIGHTS.items() if kw.lower() in combined)


def title_fingerprint(title: str) -> str:
    stopwords = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
        "with", "by", "from", "is", "are", "was", "were", "it", "its", "as", "be",
        "has", "have", "had", "will", "that", "this", "these", "those", "their",
        "they", "how", "what", "when", "where", "who", "why", "which", "not", "no",
        "new", "says", "say", "over", "up", "down", "after", "before", "than",
        "more", "first", "into", "about", "would", "could", "should",
    }
    words = re.sub(r"[^a-z0-9\s]", "", title.lower()).split()
    significant = sorted([w for w in words if w not in stopwords and len(w) > 2])
    return " ".join(significant[:6])


def stories_are_similar(a: str, b: str) -> bool:
    fa = set(title_fingerprint(a).split())
    fb = set(title_fingerprint(b).split())
    if not fa or not fb:
        return False
    return len(fa & fb) / len(fa | fb) >= 0.5


def deduplicate(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[list[dict[str, Any]]] = []
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
        best = sorted(cluster, key=lambda x: config.SOURCE_PRIORITY.get(x["source"], 0), reverse=True)[0]
        others = list(set(c["source"] for c in cluster if c["source"] != best["source"]))
        best["also_covered_by"] = others
        result.append(best)
    return result


def load_watchlist(path: Path = Path("watchlist.txt")) -> dict[str, list[str]]:
    path = Path(path)
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


def check_watchlist(text: str) -> list[str]:
    text_lower = text.lower()
    hits = []
    for kw in WATCHLIST["keywords"]:
        if kw in text_lower:
            hits.append(f"keyword:{kw}")
    for wallet in WATCHLIST["wallets"]:
        if wallet in text_lower:
            hits.append(f"wallet:{wallet}")
    return hits


def update_story_threads(news_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    threads = load_story_threads()
    cutoff = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    threads = {k: v for k, v in threads.items() if v.get("last_seen", "") >= cutoff}

    for hit in news_hits:
        fp = title_fingerprint(hit["title"])
        if not fp:
            continue
        matched_key = None
        for key, thread in threads.items():
            if stories_are_similar(hit["title"], thread["representative_title"]):
                matched_key = key
                break
        if matched_key:
            thread = threads[matched_key]
            if config.TODAY not in thread["dates_seen"]:
                thread["dates_seen"].append(config.TODAY)
            thread["last_seen"] = config.TODAY
            thread["mention_count"] = len(thread["dates_seen"])
        else:
            threads[fp] = {
                "representative_title": hit["title"],
                "dates_seen": [config.TODAY],
                "last_seen": config.TODAY,
                "mention_count": 1,
            }

    save_story_threads(threads)
    developing = [
        v for v in threads.values()
        if v["mention_count"] >= 2 and v["last_seen"] == config.TODAY
    ]
    return sorted(developing, key=lambda x: x["mention_count"], reverse=True)


def save_seen_articles(urls: set[str]) -> None:
    persist_seen_articles(urls)


def fetch_rss(feeds: dict[str, str], keywords: list[str]) -> list[dict[str, Any]]:
    raw = []
    for source, url in feeds.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                combined = (title + " " + summary).lower()
                matched = [kw for kw in keywords if kw.lower() in combined]
                if not matched:
                    continue

                if any(noise in combined for noise in config.NOISE_EXCLUSION_KEYWORDS):
                    strong = ["polymarket", "kalshi", "prediction market insider", "CFTC enforcement"]
                    if not any(kw in combined for kw in strong):
                        continue

                watchlist_hits = check_watchlist(title + " " + summary)
                score = score_article(title, summary, matched)
                clean = clean_text(entry.get("summary", ""))[:250]
                if len(clean) < 20:
                    clean = f"[See full article at {source}]"

                raw.append({
                    "source": source,
                    "title": title,
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "pub_date": parse_date(entry.get("published", "")),
                    "matched_keywords": matched,
                    "summary": clean,
                    "score": score,
                    "priority": score >= 3 or bool(watchlist_hits),
                    "watchlist_hit": watchlist_hits,
                    "also_covered_by": [],
                })
        except Exception as e:
            print(f"  RSS error [{source}]: {e}")

    deduped = deduplicate(raw)
    seen = set() if config.DEMO_MODE else load_seen_articles()
    fresh = [h for h in deduped if h.get("link", "") not in seen]
    if config.DEMO_MODE:
        print("  DEMO MODE: bypassing seen articles cache")

    fresh = sorted(fresh, key=lambda x: x["score"], reverse=True)
    print(f"  RSS: {len(raw)} raw -> {len(deduped)} unique -> {len(fresh)} new today")
    return fresh

