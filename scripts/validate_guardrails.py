#!/usr/bin/env python3
"""Validate the lightweight engineering guardrail scaffold."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    ".cursor/rules/worker-gate.mdc",
    ".cursor/rules/test-first.mdc",
    ".cursor/rules/code-reviewer.mdc",
    ".cursor/rules/red-team.mdc",
    ".cursor/rules/debugger.mdc",
    ".cursor/rules/minimalist.mdc",
    ".cursor/rules/expert-review.mdc",
    "AGENTS.md",
    "docs/architecture.md",
    "docs/engineering_guardrails.md",
    "docs/runbooks/daily-monitor.md",
    "docs/detectors/signal_card_template.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
]

FORBIDDEN_VENDOR_DIRS = [
    "universal-agent-bootstrap",
    "universal-agent-workflow-template",
    "roundtable",
]


def fail(message):
    print(f"guardrails validation failed: {message}", file=sys.stderr)
    return 1


def has_frontmatter(path):
    text = path.read_text()
    return text.startswith("---\n") and "\n---\n" in text[4:]


def main():
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        return fail("missing required files: " + ", ".join(missing))

    vendor_dirs = [name for name in FORBIDDEN_VENDOR_DIRS if (ROOT / name).exists()]
    if vendor_dirs:
        return fail("external scaffold repos must not be vendored: " + ", ".join(vendor_dirs))

    rule_paths = sorted((ROOT / ".cursor" / "rules").glob("*.mdc"))
    if len(rule_paths) < 7:
        return fail("expected at least seven Cursor rule files")

    missing_frontmatter = [str(path.relative_to(ROOT)) for path in rule_paths if not has_frontmatter(path)]
    if missing_frontmatter:
        return fail("rule files missing Cursor frontmatter: " + ", ".join(missing_frontmatter))

    print("guardrails validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
