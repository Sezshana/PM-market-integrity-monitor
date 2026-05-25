# Signal Card: Shared Funding Source

## Signal Name

Shared funding source

Status: active when `POLYGONSCAN_KEY` is configured

## Purpose

Identify two counterparty wallets whose initial observed USDC funding source is
the same address. This is a linkage signal and requires corroboration before any
common-control conclusion.

## Data Sources

- Source: Polygonscan token transfer API
- Collection method: earliest USDC token transfer lookup for each wallet
- Required credentials: `POLYGONSCAN_KEY`
- Expected refresh cadence: daily workflow for top repeated counterparty pair
- Known source limitations: only the first returned transfer is considered;
  shared exchanges or custodians can create benign shared funders.

## Detection Criteria

```text
POLYGONSCAN_KEY is configured.
Funding wallet can be retrieved for wallet A.
Funding wallet can be retrieved for wallet B.
Funding wallet A equals funding wallet B.
```

## Thresholds

```text
No numeric threshold beyond matching first observed funder.
```

## Output Fields

```text
shared_funder: Matching funder address
wallet_a: First wallet
wallet_b: Second wallet
signal: SHARED FUNDING SOURCE
explanation: Evidence-first explanation
polygonscan: Shared funder URL
```

## Known False Positives

- Exchange or custodial funding addresses.
- Market-maker funding infrastructure.
- Shared on-ramp or OTC desk.
- API result that is not true initial funding due to pagination or token-only
  scope.

## Alternative Explanations

- Common exchange withdrawal address
- Shared custody provider
- Business relationship without common control
- Publicly used funding service

## Analyst Review Actions

1. Determine whether the shared funder is an exchange, contract, or individual
   wallet.
2. Review non-USDC funding and broader transaction history.
3. Check whether wallets also share timing, counterparties, or net exposure.
4. Do not infer common control without corroborating evidence.

## Tests

- Unit tests should mock Polygonscan responses for matching and non-matching
  funders.

## Reporting Language

Preferred:

```text
Shared funder observed; analyst review required before inferring common control.
```

Avoid:

```text
The wallets are controlled by the same person.
```
