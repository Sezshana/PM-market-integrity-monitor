# Polymarket OSINT Monitor

An automated daily surveillance intelligence system for prediction market integrity monitoring, built independently as pre-start preparation for a market surveillance role.

---

## What This Does

Runs every morning at 7 AM EDT and delivers a structured intelligence digest covering:

### Market Integrity Detection
- **Market review criteria** — flags markets with high volume on low-probability outcomes using Polymarket's public Gamma API (a review signal, not a conclusion)
- **Large individual trades** — scrapes Polymarket's CLOB order book for individual trades over $10k on markets under 15% probability
- **On-chain wallet profiling** — uses Polygonscan to identify new wallets, contract addresses (bots), funding sources, and high-frequency traders behind flagged positions
- **Win rate tracker** — maintains a rolling record of wallets betting large on long shots, flags anyone with >75% win rate across multiple markets

### Regulatory Intelligence
- **Congressional bill tracker** — monitors 7 prediction market bills via Congress.gov; surfaces **only changes** (new actions or newly added bills), otherwise a one-line quiet status
- **OFAC cross-reference** — monitors OFAC SDN list daily for new crypto wallet additions, cross-references against Polymarket activity
- **UMA governance disputes** — filters UMA Protocol forum for Polymarket-specific resolution disputes and bad-faith voting patterns (the April 2026 governance attack vector)

### News and Pattern Recognition
- **Multi-source RSS monitoring** — CoinDesk, The Block, Decrypt, Bloomberg Crypto, DLA Piper Market Edge, CFTC press releases and enforcement actions
- **Priority scoring** — articles scored by keyword combinations, sorted by importance
- **Cross-day deduplication** — no article is sent twice; rolling 500-article seen list
- **Developing story threading** — tracks when the same story appears across multiple days (identifies ongoing investigations and regulatory developments)
- **Narrative summary** — plain-English digest of the day's intelligence at the top of every email

### Email Delivery
- Smart subject lines that surface the top story before you open the email
- Quiet day mode — short email when nothing significant happened
- All dates and timestamps included on every item
- Runs daily via GitHub Actions, no manual intervention required

---

## Regulatory Coverage

### Congressional Bills Tracked
| Bill | Status |
|------|--------|
| PREDICT Act (H.R. 8076) | In committee |
| End Prediction Market Corruption Act (S. 4017) | In committee |
| Prediction Markets Security and Integrity Act (S. 4060) | In committee |
| Public Integrity in Financial Prediction Markets Act (S. 4188) | In committee |
| STOP Corrupt Bets Act (S. 4226) | In committee |
| BETS OFF Act (S. 4115) | In committee |
| Event Contract Enforcement Act (H.R. 7840) | In committee |

### Detection Logic Covers
- Insider trading (all three categories from Polymarket's March 2026 Market Integrity Rules)
- Wash trading and fictitious transactions
- Spoofing and layering
- Oracle/resolution manipulation and governance attacks
- OFAC sanctions violations
- Coordinated bad-faith voting in UMA dispute resolution

---

## Architecture

```
polymarket-osint-monitor/
├── monitor.py              # Daily orchestration entry point
├── aggregator.py           # Cross-day aggregate dashboard state
├── wash_trading_module.py  # Backwards-compatible wash detector entry point
├── src/
│   └── polymarket_monitor/
│       ├── clients/        # RSS, Polymarket, OFAC, UMA, Congress, on-chain clients
│       ├── detectors/      # Market review and wash-trading detector logic
│       ├── reporting/      # Report schema helpers
│       └── storage/        # JSON state helpers
├── requirements.txt        # Python dependencies
├── watchlist.txt           # Keywords, wallets, handles to monitor (customizable)
├── dashboard.html          # Local web dashboard — reads daily JSON reports
├── .github/
│   └── workflows/
│       └── daily_monitor.yml   # GitHub Actions — runs daily at 7 AM EDT
├── output/
│   └── report_YYYY-MM-DD.md/json   # Daily reports
├── cases/
│   ├── INDEX.md            # Auto-generated case index
│   └── case_template.md    # Investigation memo template
└── data/
    ├── seen_articles.json      # Cross-day deduplication cache
    ├── ofac_seen_uids.json     # OFAC new-entry tracking
    ├── win_rate_tracker.json   # Suspicious wallet win rate history
    └── story_threads.json      # Developing story tracking
```

---

## Setup

### GitHub Secrets Required
| Secret | Source |
|--------|--------|
| `ALERT_EMAIL` | Your email address |
| `SMTP_PASSWORD` | Gmail App Password |
| `CONGRESS_API_KEY` | Free at api.congress.gov |
| `DUNE_API_KEY` | Free at dune.com |
| `POLYGONSCAN_KEY` | Free at polygonscan.com/apis |

Use `.env.example` as the local configuration template. Do not commit `.env` files or real credentials.

### Data Versioning Policy

This repository currently runs in **public demo/dashboard mode**:

- `output/` reports and `data/` aggregate state are intentionally versioned.
- The daily GitHub Action commits those generated files so GitHub Pages can render the dashboard without external infrastructure.
- Treat committed reports as public artifacts and keep them sanitized.

For a private operational deployment, stop committing generated intelligence and add `output/`, `data/`, and `watchlist.txt` to `.gitignore`.

### Local Dashboard
Requires VS Code with Live Server extension.
Open repo folder in VS Code, right-click `dashboard.html`, select Open with Live Server.
Pull latest from GitHub Desktop each morning before viewing.

---

## Investigation Framework

The `cases/` folder uses a structured investigation memo format covering:
- Review criteria and applicable rule context (CEA, Polymarket Market Integrity Rules)
- Market details (question, probability at trade, position size, outcome, profit)
- On-chain data (wallet addresses, funding source, linked wallets, transaction hashes)
- OSINT findings (off-chain identity resolution)
- Behavioral indicators
- Timeline
- Disposition (close, escalate to Legal, refer to CFTC, refer to DOJ)

---

## Background

Built independently during a 3-week pre-start period as preparation for a Lead Market Surveillance Analyst role. The system applies insider threat detection methodology and blockchain forensics experience to prediction market integrity monitoring.

Key reference cases informing detection logic:
- Iran war bets insider trading case (May 2026) — $2.4M profit, 98% win rate
- April 2026 UMA governance attack (Israel-Hezbollah ceasefire market)
- Maduro-linked market-integrity review (2024)
- $520K Polygon exploit (May 2026)
