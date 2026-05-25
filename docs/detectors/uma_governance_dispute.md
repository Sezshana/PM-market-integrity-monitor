# Signal Card: UMA Governance Dispute Review

## Signal Name

UMA governance dispute review

Status: active

## Purpose

Identify UMA forum posts that may relate to Polymarket resolution disputes,
oracle manipulation concerns, or governance-attack patterns.

## Data Sources

- Source: UMA forum/RSS content fetched by `monitor.py`
- Collection method: HTTP/RSS parsing
- Required credentials: none
- Expected refresh cadence: daily workflow
- Known source limitations: forum post wording varies and may omit Polymarket
  even when context is relevant.

## Detection Criteria

```text
Forum item text matches required UMA/Polymarket dispute terms.
Configured terms include polymarket, dispute, resolution, incorrect,
manipulat, bad faith, exploit, governance attack, slashing, bad-faith.
Matching items are included in the daily digest as governance alerts.
```

## Thresholds

```text
Keyword-based matching only; no numeric threshold.
```

## Output Fields

```text
title: Forum item title
published: Published date
summary: Cleaned summary
link: Forum URL
alert_type: Alert/category label
note: Review note
```

## Known False Positives

- Generic UMA disputes unrelated to Polymarket.
- Educational or retrospective posts that mention attack terms.
- Posts discussing governance mechanisms without active dispute risk.

## Alternative Explanations

- Routine oracle dispute discussion
- Governance-process education
- Historical incident recap

## Analyst Review Actions

1. Open the forum post and confirm Polymarket relevance.
2. Identify market, resolution source, and disputed outcome.
3. Check whether voting behavior or incentives indicate escalation need.
4. Preserve observed facts separately from conclusions.

## Tests

- Unit tests should cover required keyword matching and non-Polymarket dispute
  exclusions.

## Reporting Language

Preferred:

```text
UMA governance dispute matched review criteria.
```

Avoid:

```text
Governance attack confirmed.
```
