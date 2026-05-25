# Signal Card: Large Low-Probability CLOB Trade

## Signal Name

Large low-probability CLOB trade

Status: active

## Purpose

Identify individual Polymarket CLOB trades that are large enough for review and
occur on outcomes priced at low probability.

## Data Sources

- Source: Polymarket CLOB API
- Collection method: `GET https://clob.polymarket.com/trades`
- Required credentials: none
- Expected refresh cadence: daily workflow
- Known source limitations: recent trade window only; asset metadata may require
  separate lookup for full market context.

## Detection Criteria

```text
Trade size >= LARGE_TRADE_USD.
Computed probability <= LOW_PROB_MAX_PCT.
BUY probability uses price * 100.
SELL probability uses (1 - price) * 100.
Watchlist matches on maker or taker are included when present.
Results are sorted by size and capped to the top 10.
```

## Thresholds

```text
LARGE_TRADE_USD = 10,000
LOW_PROB_MAX_PCT = 15
```

## Output Fields

```text
timestamp: Trade timestamp
size_usd: Trade size
prob_pct: Computed probability percentage
side: BUY or SELL
asset_id: CLOB asset identifier
maker: Maker wallet
taker: Taker wallet
wl_maker: Watchlist matches for maker
wl_taker: Watchlist matches for taker
```

## Known False Positives

- Market makers taking inventory.
- Hedged trades across related markets.
- Publicly explainable news events.
- Low-probability outcomes with temporarily stale price data.

## Alternative Explanations

- Liquidity provision
- Portfolio hedging
- Arbitrage across correlated markets
- Public information or social-media-driven speculation

## Analyst Review Actions

1. Map the asset ID to market context.
2. Review maker and taker histories.
3. Check for watchlist hits and shared funding.
4. Compare trade timing with public events.

## Tests

- Unit tests should cover BUY and SELL probability calculations.
- Contract tests should preserve output fields consumed by reports.

## Reporting Language

Preferred:

```text
Large individual trade detected on a low-probability market. Review wallet context.
```

Avoid:

```text
Trader is suspicious.
Trade proves manipulation.
```
