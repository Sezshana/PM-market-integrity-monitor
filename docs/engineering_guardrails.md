# Engineering Guardrails

These guardrails adapt the useful parts of Brian Carter / KangaKode's public
agent workflow repos to this existing monitor without vendoring those repos.

## What Was Incorporated

- Project-local Cursor rules in `.cursor/rules/`
- A repository map and agent working agreement in `AGENTS.md`
- Architecture notes for current and future module boundaries
- A daily-monitor runbook
- A detector signal-card template
- A pull request checklist
- Lightweight CI validation for guardrail files and Python syntax

## What Was Not Incorporated

- No external repo was copied into this repository.
- No specialist `.cursor/agents/` pack was added yet.
- No runtime Cursor hooks were added.
- No full `src/polymarket_monitor/` restructure was started.
- No new package-management or pre-commit dependency stack was introduced.

## Default Workflow

1. Clarify the request and inspect the current code.
2. For non-trivial behavior changes, create design docs under
   `docs/designs/<feature-name>/`.
3. Review the design before implementation.
4. Implement with focused tests.
5. Run validation.
6. Use the PR template to document data handling, evidence language, and tests.

## When to Add More

Consider adding the larger workflow-template pieces only after the repo has:

- A `src/` package layout
- A stable test suite
- Clear public-demo/private-operational deployment choice
- Detector signal cards for active heuristics
- A reviewed-alert or case-management workflow
