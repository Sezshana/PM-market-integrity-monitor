"""Once-per-day email dispatch tracking (shared across CI runners via git)."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

EMAIL_DISPATCH_STATE = Path("data/email_dispatch_state.json")

MORNING_EMAIL_START_HOUR = int(os.environ.get("MORNING_EMAIL_START_HOUR", "6"))
MORNING_EMAIL_END_HOUR = int(os.environ.get("MORNING_EMAIL_END_HOUR", "12"))


def _force_email() -> bool:
    return os.environ.get("FORCE_EMAIL", "").lower() == "true"


def _github_event() -> str:
    return os.environ.get("GITHUB_EVENT_NAME", "")


def _demo_mode() -> bool:
    return os.environ.get("DEMO_MODE", "").lower() == "true"


def eastern_today() -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.date.today().isoformat()


def load_dispatch_date(path: Path | None = None) -> str | None:
    state_path = path or EMAIL_DISPATCH_STATE
    if not state_path.exists():
        return None
    try:
        payload = json.loads(state_path.read_text())
        return str(payload.get("eastern_date") or "")
    except (json.JSONDecodeError, OSError):
        return None


def mark_email_sent(subject: str, path: Path | None = None) -> None:
    state_path = path or EMAIL_DISPATCH_STATE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from zoneinfo import ZoneInfo

        now_local = datetime.datetime.now(ZoneInfo("America/New_York")).isoformat()
    except Exception:
        now_local = datetime.datetime.now().astimezone().isoformat()
    state_path.write_text(
        json.dumps(
            {
                "eastern_date": eastern_today(),
                "sent_at": now_local,
                "subject": subject,
            },
            indent=2,
        )
    )


def should_skip_scheduled_email(path: Path | None = None) -> tuple[bool, str]:
    """Return (skip, reason)."""
    today = eastern_today()
    state_path = path or EMAIL_DISPATCH_STATE

    if _github_event() != "schedule" or _force_email():
        return False, ""

    try:
        from zoneinfo import ZoneInfo

        hour = datetime.datetime.now(ZoneInfo("America/New_York")).hour
    except Exception:
        hour = datetime.datetime.now().hour

    in_morning = MORNING_EMAIL_START_HOUR <= hour < MORNING_EMAIL_END_HOUR
    if in_morning:
        return False, ""

    if load_dispatch_date(state_path) == today:
        return True, (
            f"outside morning window ({hour}:00 ET) and digest already sent for {today}"
        )

    return False, f"delay recovery — no digest sent yet for {today}"


def should_skip_duplicate_send(path: Path | None = None) -> tuple[bool, str]:
    """Return (skip, reason) for duplicate same-day sends."""
    if _demo_mode() or _force_email():
        return False, ""
    today = eastern_today()
    if load_dispatch_date(path or EMAIL_DISPATCH_STATE) == today:
        return True, f"digest already sent for {today} (Eastern)"
    return False, ""
