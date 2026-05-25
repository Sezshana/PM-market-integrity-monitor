# Detector Signal Card Template

Use one signal card per detector or heuristic. Keep cards short and factual.

## Signal Name

Name:

Owner:

Status: draft / active / retired

## Purpose

What observed behavior does this signal identify?

What decision does it support?

## Data Sources

- Source:
- Collection method:
- Required credentials:
- Expected refresh cadence:
- Known source limitations:

## Detection Criteria

List criteria as observable facts.

```text
Criterion 1:
Criterion 2:
Criterion 3:
```

## Thresholds

```text
Threshold:
Rationale:
Last reviewed:
```

## Output Fields

```text
field_name:
type:
description:
```

## Known False Positives

- Scenario:
- Why it matches:
- How an analyst should distinguish it:

## Alternative Explanations

- Legitimate market-making
- Public information advantage
- API/source data artifact
- Shared infrastructure or exchange funding wallet
- Other:

## Analyst Review Actions

1. 
2. 
3. 

## Tests

- Unit tests:
- Fixture files:
- Schema checks:
- Integration checks:

## Reporting Language

Preferred phrasing:

```text
Criteria matched: ...
Analyst review required.
```

Avoid:

```text
This proves ...
Very likely controlled by ...
Insider/manipulation conclusion without review.
```
