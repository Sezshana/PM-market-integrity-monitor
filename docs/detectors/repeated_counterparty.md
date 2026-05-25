# Signal Card: Repeated Counterparty Pattern

## Signal Name

Repeated counterparty pattern

Status: active

## Purpose

Identify wallet pairs that repeatedly trade against each other in the same
market. This can be consistent with coordinated activity but requires order-book
and wallet-context review.

## Data Sources

- Source: Polymarket CLOB API
- Collection method: market-specific trade fetch in `wash_trading_module.py`
- Required credentials: none for CLOB data
- Expected refresh cadence: daily workflow for top flagged markets
- Known source limitations: limited fetched trade window and API response shape.

## Detection Criteria

```text
Maker and taker addresses both present.
Maker and taker are different wallets.
Wallet pair is normalized so A-B and B-A are counted together.
Pair trade count >= WASH_PAIR_MIN_TRADES.
Pair volume is accumulated across matched trades.
```

## Thresholds

```text
WASH_PAIR_MIN_TRADES = 3
```

## Output Fields

```text
wallet_a: First wallet in normalized pair
wallet_b: Second wallet in normalized pair
trade_count: Number of paired trades
volume_usd: Accumulated trade size
signal: REPEATED COUNTERPARTY
explanation: Evidence-first explanation
polygonscan_a: Wallet A URL
polygonscan_b: Wallet B URL
```

## Known False Positives

- Two active market makers crossing naturally in a thin market.
- A participant repeatedly trading against a dominant liquidity provider.
- API records that omit enough context to distinguish maker strategies.

## Alternative Explanations

- Liquidity provision
- Hedging between known counterparties
- Repeated interaction in low-liquidity markets
- Wallets controlled by separate parties using the same venue

## Analyst Review Actions

1. Review trade timing, sides, and order-book context.
2. Check whether the pair also shows near-zero net exposure.
3. Check funding source and wallet histories.
4. Compare with market liquidity and participant concentration.

## Tests

- Existing unit tests cover repeated-pair detection and evidence-first wording.
- Additional tests should cover pairs below threshold and maker/taker order
  normalization.

## Reporting Language

Preferred:

```text
Repeated counterparty pattern observed; analyst review required.
```

Avoid:

```text
These wallets are wash traders.
```
