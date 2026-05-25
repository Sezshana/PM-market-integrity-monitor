# Daily Monitor Runbook

## Purpose

Run and validate the Polymarket OSINT Monitor's daily collection, report
generation, aggregation, email delivery, and static dashboard update.

## Required Environment

```text
ALERT_EMAIL
SMTP_PASSWORD
CONGRESS_API_KEY
DUNE_API_KEY
POLYGONSCAN_KEY
```

Email delivery is skipped when `SMTP_PASSWORD` is absent. Source-specific
features degrade when their API keys are absent.

## Manual Run

```bash
python3 -m pip install -r requirements.txt
python3 monitor.py
python3 aggregator.py
```

## Expected Artifacts

```text
output/report_<YYYY-MM-DD>.json
output/report_<YYYY-MM-DD>.md
data/aggregate_intelligence.json
data/seen_articles.json
data/story_threads.json
cases/INDEX.md
```

## Validation

```bash
python3 -m py_compile monitor.py wash_trading_module.py aggregator.py email_template.py onchain_monitor.py
python3 scripts/validate_guardrails.py
```

If tests exist:

```bash
python3 -m unittest discover -s tests
```

## Common Failures

### No email received

1. Confirm `ALERT_EMAIL` and `SMTP_PASSWORD`.
2. Check GitHub Actions logs for SMTP errors.
3. Confirm Gmail app password status if Gmail is used.

### Empty dashboard

1. Confirm today's or yesterday's report exists in `output/`.
2. Confirm `data/aggregate_intelligence.json` exists.
3. Serve `dashboard.html` through a local web server instead of opening it with
   `file://`.

### API data missing

1. Check whether the relevant API key is configured.
2. Look for rate-limit or non-200 messages in monitor logs.
3. Avoid changing detector thresholds until source availability is confirmed.

## Data Handling

Generated reports and state may be public if the repo is in demo/dashboard mode.
Before using the monitor operationally, decide whether to stop committing
`output/`, `data/`, private `cases/`, and `watchlist.txt`.
