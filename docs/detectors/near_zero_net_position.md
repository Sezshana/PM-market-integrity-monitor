# Signal Card: Near-Zero Net Position

## Signal Name

Near-zero net position after high gross volume

Status: active

## Purpose

Identify wallets with high gross trading volume but low net exposure in a
market. This can indicate activity that deserves review, but it does not by
itself establish intent.

## Data Sources

- Source: Polymarket CLOB API
- Collection method: market-specific trade fetch in `wash_trading_module.py`
- Required credentials: none for CLOB data
- Expected refresh cadence: daily workflow for top flagged markets
- Known source limitations: depends on fetched trade window; positions outside
  the window may change net exposure.

## Detection Criteria

```text
Wallet bought and sold amounts are accumulated from trade side.
Gross volume = bought + sold.
Net exposure = absolute value of bought - sold.
Gross volume >= MIN_TRADE_SIZE_USD.
Net exposure / gross volume < NET_POSITION_THRESHOLD.
Results are sorted by gross volume and capped to top 5.
```

## Thresholds

```text
MIN_TRADE_SIZE_USD = 1,000
NET_POSITION_THRESHOLD = 0.05
```

## Output Fields

```text
wallet: Wallet address
gross_volume: Bought plus sold volume
net_position: Absolute net exposure
net_ratio: Net exposure as percentage of gross volume
signal: NEAR-ZERO NET POSITION
explanation: Evidence-first explanation
polygonscan: Wallet URL
```

## Known False Positives

- Market makers actively managing inventory.
- Traders closing positions after news changes.
- Hedged strategies where net exposure is intentionally low.
- Incomplete trade windows that miss earlier or later position changes.

## Alternative Explanations

- Liquidity provision
- Inventory rebalancing
- Arbitrage
- Risk reduction after public information changes

## Analyst Review Actions

1. Review the full market position history if available.
2. Check whether trades are paired with repeated counterparties.
3. Compare timing to public news and price movements.
4. Review wallet funding and related market activity.

## Tests

- Existing unit tests cover low net exposure detection and evidence-first
  explanation text.
- Additional tests should cover wallets below gross-volume threshold.

## Reporting Language

Preferred:

```text
Near-zero net exposure observed; analyst review required.
```

Avoid:

```text
The wallet had no real conviction.
```
