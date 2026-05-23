# Polymarket OSINT Monitor

Automated daily intelligence gathering for Polymarket trade surveillance work.

## What It Does

Runs every morning at 8:00 AM EST and:

1. Scans RSS feeds from CoinDesk, The Block, Decrypt, Bloomberg Crypto, DLA Piper, CFTC
2. Filters all content for prediction market keywords
3. Checks CFTC enforcement actions and rulemaking notices
4. Tracks status of all pending Congressional prediction market bills
5. Pulls Polymarket on-chain stats from Dune Analytics
6. Generates a daily markdown report saved to /output/
7. Sends an email digest if alerts are found

## Setup Instructions

### Step 1 — Fork or clone this repo

### Step 2 — Set GitHub Secrets
Go to Settings > Secrets and Variables > Actions > New Repository Secret

Add these secrets:
- `ALERT_EMAIL` — your email address (shanabautista0819@gmail.com)
- `SMTP_PASSWORD` — your Gmail App Password (NOT your regular password)
  - Go to Google Account > Security > 2-Step Verification > App Passwords
  - Create a new app password for "Mail"
  - Paste that 16-character password here
- `CONGRESS_API_KEY` — get a free key at api.congress.gov
- `DUNE_API_KEY` — get a free key at dune.com/settings/api

### Step 3 — Enable Actions
Go to Actions tab in your repo and enable GitHub Actions if prompted.

### Step 4 — Test it manually
Go to Actions > Polymarket OSINT Daily Monitor > Run workflow

### Step 5 — Check output
Reports are saved to /output/report_YYYY-MM-DD.md after each run.

## Keywords Monitored

- polymarket, kalshi
- prediction market, event contract
- CFTC prediction, insider trading prediction
- binary option CFTC, prediction market manipulation
- PREDICT act, STOP corrupt bets, BETS OFF act
- UMA protocol, oracle manipulation
- wash trading crypto

## Congressional Bills Tracked

- PREDICT Act (H.R. 8076)
- End Prediction Market Corruption Act (S. 4017)
- Prediction Markets Security and Integrity Act of 2026 (S. 4060)
- Public Integrity in Financial Prediction Markets Act (S. 4188)
- STOP Corrupt Bets Act (S. 4226)
- BETS OFF Act (S. 4115)
- Event Contract Enforcement Act (H.R. 7840)

## RSS Feeds Monitored

- CoinDesk
- The Block
- Decrypt
- Bloomberg Crypto
- DLA Piper Market Edge
- CFTC Press Releases
- CFTC Enforcement Actions

## Customizing

Edit `monitor.py` to:
- Add new keywords to the `KEYWORDS` list
- Add new RSS feeds to the `RSS_FEEDS` dict
- Add new bills to the `BILLS` list
- Adjust the schedule in `.github/workflows/daily_monitor.yml`

## Output Format

Each daily report is saved as both:
- `output/report_YYYY-MM-DD.json` — machine-readable
- `output/report_YYYY-MM-DD.md` — human-readable markdown
