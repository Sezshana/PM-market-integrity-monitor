"""Shared configuration constants for the Polymarket monitor."""

from __future__ import annotations

import datetime
import os
from pathlib import Path

POLYGONSCAN_KEY = os.environ.get("POLYGONSCAN_KEY", "")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
CONGRESS_KEY = os.environ.get("CONGRESS_API_KEY", "")
DUNE_API_KEY = os.environ.get("DUNE_API_KEY", "")
DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() == "true"

TODAY = datetime.date.today().isoformat()
TODAY_PRETTY = datetime.date.today().strftime("%B %d, %Y")
WEEKDAY = datetime.date.today().weekday()

OUTPUT_DIR = Path("output")
CASES_DIR = Path("cases")
DATA_DIR = Path("data")

SEEN_ARTICLES = DATA_DIR / "seen_articles.json"
OFAC_CACHE = DATA_DIR / "ofac_cache.json"
OFAC_SEEN = DATA_DIR / "ofac_seen_uids.json"
WIN_RATE_FILE = DATA_DIR / "win_rate_tracker.json"
STORY_THREADS = DATA_DIR / "story_threads.json"
BILL_STATE_FILE = DATA_DIR / "congress_bill_state.json"

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

NOISE_EXCLUSION_KEYWORDS = [
    "meme coin", "memecoin", "pump and dump", "shitcoin", "altcoin season",
    "xmr vs", "zec vs", "monero vs", "token launch", "nft drop",
    "rate cuts", "fed rate", "bitcoin price", "ethereum price", "solana price",
    "under exposed", "heating up", "moon", "wen lambo", "degen",
    "airdrop", "yield farming", "liquidity mining",
]

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

BILLS = [
    {"name": "PREDICT Act", "id": "hr8076", "congress": "119"},
    {"name": "End Prediction Market Corruption Act", "id": "s4017", "congress": "119"},
    {"name": "Prediction Markets Security and Integrity Act", "id": "s4060", "congress": "119"},
    {"name": "Public Integrity in Financial Prediction Markets Act", "id": "s4188", "congress": "119"},
    {"name": "STOP Corrupt Bets Act", "id": "s4226", "congress": "119"},
    {"name": "BETS OFF Act", "id": "s4115", "congress": "119"},
    {"name": "Event Contract Enforcement Act", "id": "hr7840", "congress": "119"},
]

LARGE_TRADE_USD = 10_000
LOW_PROB_MAX_PCT = 15
WIN_RATE_ALERT = 75
NEAR_TERM_DAYS = 90
HIGH_VOLUME_THRESHOLD = 1_000_000

INSIDER_RISK_KEYWORDS = [
    "fed rate", "federal reserve rate", "rate decision", "rate cut", "rate hike",
    "FDA approval", "FDA decision", "drug approval", "clinical trial",
    "CFTC ruling", "SEC ruling", "SEC charges", "regulatory approval",
    "tariff", "executive order", "sanction",
    "invasion", "military strike", "attack on", "launch attack", "military operation",
    "ceasefire", "peace deal", "withdrawal", "troop", "airstrike",
    "nuclear", "missile", "coup", "assassination",
    "merger", "acquisition", "takeover", "buyout", "ipo", "bankruptcy", "default",
    "earnings", "revenue miss", "revenue beat", "layoffs announced",
    "CEO resign", "CEO fired", "CEO appointed",
    "indictment", "arrest", "charges filed", "verdict", "conviction", "plea",
    "guilty", "sentence", "extradition",
    "classified", "intelligence", "covert", "operation",
]

LOW_INSIDER_RISK_KEYWORDS = [
    "win the election", "win the presidency", "win the primary",
    "presidential election", "senate election", "house election",
    "prime minister election", "general election", "gubernatorial",
    "win in 2026", "win in 2027", "win in 2028", "win in 2029", "win in 2030",
    "f1", "formula 1", "nfl", "nba", "mlb", "nhl", "premier league",
    "world cup", "super bowl", "stanley cup", "champion", "championship",
    "driver champion", "mvp", "tournament",
    "divorce", "baby", "oscar", "grammy", "emmy", "award", "celebrity",
    "married", "wedding", "breakup",
    "bitcoin price", "ethereum price", "crypto price", "dip to $", "reach $",
    "hyperliquid", "solana price", "doge", "shib", "ath", "all time high",
    "before 2027", "before 2028", "before 2029", "before 2030",
]

