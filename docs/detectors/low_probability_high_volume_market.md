# Signal Card: Low-Probability / High-Volume Market Review

## Signal Name

Low-probability / high-volume market review

Status: active

## Purpose

Identify active Polymarket markets where an outcome is priced at a low
probability while the market has meaningful volume. This is a triage signal for
analyst review, not a conclusion about trader intent or market integrity.

## Data Sources

- Source: Polymarket Gamma API
- Collection method: `GET https://gamma-api.polymarket.com/markets`
- Required credentials: none
- Expected refresh cadence: daily workflow
- Known source limitations: response shape and market metadata are controlled by
  Polymarket; volume and prices may change after collection.

## Detection Criteria

Observable criteria in current code:

```text
Active, open market.
Outcome probability <= LOW_PROB_MAX_PCT.
Market volume >= LARGE_TRADE_USD.
Closed markets are skipped when endDate is parseable and before today.
Markets are sorted by volume and capped to the top 10.
```

Additional prioritization:

```text
HIGH: question text matches INSIDER_RISK_KEYWORDS.
LOW: question text matches LOW_INSIDER_RISK_KEYWORDS and not high-risk keywords.
MEDIUM: neither high nor low keyword group matches.
LOW category markets require at least $50,000,000 volume.
Far-future low/medium markets under HIGH_VOLUME_THRESHOLD are skipped.
```

## Thresholds

```text
LOW_PROB_MAX_PCT = 15
LARGE_TRADE_USD = 10,000
NEAR_TERM_DAYS = 90
HIGH_VOLUME_THRESHOLD = 1,000,000
LOW category wash-trading-scale threshold = 50,000,000
```

## Output Fields

```text
market_id: Polymarket market identifier
question: Market question
outcome: Outcome name
probability_pct: Outcome probability percentage
volume_usd: Market volume
url: Polymarket event URL
end_date: Market end date or unknown
days_until_close: Days until parsed end date, or 9999
flagged_date: Collection date
insider_risk: LOW / MEDIUM / HIGH priority category
alert_reason: Evidence-first review explanation
```

## Known False Positives

- Popular long-shot election or sports markets with organic public interest.
- High-volume markets where probability is stale or briefly dislocated.
- Markets where public news explains the low-probability volume.
- Markets where volume is driven by liquidity programs or market makers.

## Alternative Explanations

- Public information advantage
- Market-making inventory management
- Hedging or portfolio rebalancing
- API data delay or display discrepancy
- Broad speculative interest in long-shot outcomes

## Analyst Review Actions

1. Review the largest traders and counterparties.
2. Compare timing with public news and market updates.
3. Check whether the question category has concentrated decision access.
4. Look for repeated counterparties, near-zero exposure, shared funding, or
   synchronized timing before escalation.

## Tests

- Unit coverage should validate threshold behavior and output schema.
- Dashboard contract tests should preserve required output fields.

## Reporting Language

Preferred:

```text
Criteria matched: low-probability outcome, market volume, and relevant review context. Analyst review required.
```

Avoid:

```text
Insider trading occurred.
Someone has nonpublic information.
```
