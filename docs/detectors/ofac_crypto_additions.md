# Signal Card: OFAC Crypto Additions

## Signal Name

OFAC crypto additions

Status: active

## Purpose

Track new OFAC SDN entries with crypto wallet information and make them
available for cross-reference against Polymarket-related wallet activity.

## Data Sources

- Source: OFAC sanctions data fetched by `monitor.py`
- Collection method: HTTP download/parse and local seen-UID cache
- Required credentials: none
- Expected refresh cadence: daily workflow
- Known source limitations: OFAC formatting can change; not every sanctioned
  entity has wallet metadata.

## Detection Criteria

```text
OFAC entry is present in the current source data.
Entry has not previously been recorded in ofac_seen_uids.json.
Entry includes crypto wallet/address context when available.
New additions are included in the daily report.
```

## Thresholds

```text
New UID/address relative to local seen cache.
```

## Output Fields

```text
name: OFAC-listed name
wallet: Crypto wallet/address when available
uid: OFAC identifier when available
program: Sanctions program when available
```

## Known False Positives

- Parser mistakes caused by OFAC source-format changes.
- Reissued or updated records that look new to the local cache.
- Wallet strings that require chain/context verification.

## Alternative Explanations

- Administrative OFAC record update
- Alias or metadata change
- Same wallet represented under a different record

## Analyst Review Actions

1. Confirm the entry directly against OFAC source data.
2. Verify chain/address format.
3. Cross-reference only after confirming address normalization.
4. Treat matches as requiring escalation review, not automatic attribution.

## Tests

- Unit tests should cover seen-cache behavior and parser resilience with fixture
  data.

## Reporting Language

Preferred:

```text
New OFAC crypto sanctions added; cross-reference with confirmed wallet history.
```

Avoid:

```text
Wallet is sanctioned without source confirmation.
```
