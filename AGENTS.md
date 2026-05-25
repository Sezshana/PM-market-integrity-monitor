# Agent Guide

This repository uses project-local guardrails inspired by Brian Carter /
KangaKode's `universal-agent-bootstrap` and `universal-agent-workflow-template`.
The external repos are references only; they are not vendored or runtime
dependencies.

## Repository Map

```text
monitor.py                 Daily orchestration, source collection, reporting
wash_trading_module.py     Wash-trading review signals
onchain_monitor.py         Polygonscan wallet/profile helpers
aggregator.py              Cross-day aggregate dashboard state
email_template.py          HTML email rendering
dashboard.html             Static dashboard consuming output/data JSON
watchlist.txt              Local watchlist terms, wallets, and handles
output/                    Generated reports for demo/dashboard mode
data/                      Generated aggregate/deduplication state
cases/                     Case template and generated case index
docs/                      Architecture, runbooks, detector templates
.cursor/rules/             Project-local Cursor guardrails
```

## Working Agreement for Agents

1. Read `docs/architecture.md` before broad code changes.
2. For non-trivial detector, storage, reporting, or workflow changes, create
   design docs in `docs/designs/<feature-name>/` before implementation.
3. Keep generated findings evidence-first. Heuristics match criteria; analysts
   draw conclusions after review.
4. Add focused tests for behavioral logic. Keep pure unit tests offline.
5. Do not vendor external scaffolding repos into this project.
6. Preserve the static dashboard contract unless the PR documents a migration.
7. Treat `output/`, `data/`, `cases/`, and `watchlist.txt` as potentially
   sensitive. Public-demo artifacts must be sanitized.

## Validation Commands

Use the narrowest relevant command first, then broader checks:

```bash
python3 -m py_compile monitor.py wash_trading_module.py aggregator.py email_template.py onchain_monitor.py
python3 scripts/validate_guardrails.py
python3 -m unittest discover -s tests
```

If `tests/` does not exist yet, skip the unittest command and add focused tests
with the first behavioral change.
