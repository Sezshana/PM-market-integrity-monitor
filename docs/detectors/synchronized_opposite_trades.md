# Signal Card: Synchronized Opposite Trades

## Signal Name

Synchronized opposite-side trades

Status: active

## Purpose

Identify trades involving overlapping wallets on opposite sides within a short
time window. This is a timing/linkage signal for review.

## Data Sources

- Source: Polymarket CLOB API
- Collection method: market-specific trade fetch in `wash_trading_module.py`
- Required credentials: none for CLOB data
- Expected refresh cadence: daily workflow for top flagged markets
- Known source limitations: timestamp precision and fetched trade window can
  affect detection.

## Detection Criteria

```text
Trades sorted by match_time.
Compare each trade with the next 20 trades.
Stop inner scan once timestamp difference exceeds TIMING_WINDOW_SECONDS.
Wallet sets overlap between the two trades.
Trade sides differ.
Both trade sizes >= MIN_TRADE_SIZE_USD.
Return up to 5 findings.
```

## Thresholds

```text
TIMING_WINDOW_SECONDS = 60
MIN_TRADE_SIZE_USD = 1,000
```

## Output Fields

```text
wallet: Shared wallet address
trade_a_size: First trade size
trade_b_size: Second trade size
seconds_apart: Absolute time difference
signal: SYNCHRONIZED OPPOSITE TRADES
explanation: Evidence-first explanation
```

## Known False Positives

- Fast market makers updating inventory.
- Automated strategies reacting to price movement.
- Thin markets where the same active wallet appears frequently.
- Timestamp clustering from API processing.

## Alternative Explanations

- Market-making automation
- Inventory rebalancing
- Hedged strategy execution
- Public news-driven rapid trading

## Analyst Review Actions

1. Review the order book around both trades.
2. Check whether counterparties repeat across other trades.
3. Compare with near-zero net exposure.
4. Review wallet funding and market context.

## Tests

- Unit tests should cover same-side trades, outside-window trades, and below-size
  trades.

## Reporting Language

Preferred:

```text
Synchronized opposite-side timing observed; analyst review required.
```

Avoid:

```text
Classic wash trading proves coordination.
```
