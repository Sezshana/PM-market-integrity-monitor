# Signal Card: On-Chain New-Wallet / Large-Trade Review

## Signal Name

On-chain new-wallet / large-trade review

Status: active

## Purpose

Add wallet context to large low-probability trades by checking whether involved
wallets are new, low-history, or watchlist-linked.

## Data Sources

- Source: Polymarket CLOB API
- Source: Polygonscan API
- Collection method: recent CLOB trades plus wallet transaction history lookups
- Required credentials: `POLYGONSCAN_KEY`
- Expected refresh cadence: daily workflow
- Known source limitations: API rate limits, transaction count pagination, and
  wallet age based on first returned Polygon transaction.

## Detection Criteria

```text
Recent CLOB trade size >= LARGE_TRADE_USD.
Computed probability <= LOW_PROB_MAX_PCT.
Maker and taker wallet age checked with Polygonscan.
Wallet under 30 days old adds review weight.
Wallet under 90 days old adds lower review weight.
Wallet with fewer than 10 returned transactions adds review weight.
Watchlist match adds review weight.
Very low probability <= 5% adds review weight.
Only trades with review context are returned.
```

## Thresholds

```text
LARGE_TRADE_USD = 10,000
LOW_PROB_MAX_PCT = 15
New wallet = under 30 days
Recent wallet = under 90 days
Low transaction count = fewer than 10 returned transactions
Very low probability = 5% or lower
```

## Output Fields

```text
maker: Maker wallet
taker: Taker wallet
size_usd: Trade size
prob_pct: Computed probability
side: BUY or SELL
asset_id: CLOB asset identifier
timestamp: Trade date
risk_score: Review-weight score
risk_factors: Matched wallet/context criteria
wl_maker: Maker watchlist hits
wl_taker: Taker watchlist hits
maker_age: Maker first transaction date or unknown
taker_age: Taker first transaction date or unknown
polygonscan: Maker wallet URL
from_link: Maker wallet URL
watchlist: Combined watchlist hits
```

## Known False Positives

- Newly created wallets used for privacy or custody hygiene.
- Exchange or market-maker wallets with limited visible history.
- API pagination that undercounts history.
- Legitimate first-time participants reacting to public news.

## Alternative Explanations

- New wallet for operational security
- Custodial or exchange wallet routing
- Market-making strategy
- Public information-driven trade

## Analyst Review Actions

1. Verify wallet age and transaction history manually.
2. Trace funding source and counterparties.
3. Compare with watchlist context.
4. Review whether public information explains trade timing.

## Tests

- Unit tests should cover score thresholds using mocked wallet metadata.
- Contract tests should preserve report fields and dashboard-safe schema.

## Reporting Language

Preferred:

```text
Wallet context matched review criteria.
```

Avoid:

```text
New wallet is an insider wallet.
```
