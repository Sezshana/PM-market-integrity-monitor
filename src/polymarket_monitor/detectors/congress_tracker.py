"""Congressional bill watchlist state and change detection."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass
class BillTrackerResult:
    changes: list[dict[str, Any]] = field(default_factory=list)
    quiet_message: str = ""
    monitored_count: int = 0
    movement_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_bill_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"bills": {}, "meta": {}}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"bills": {}, "meta": {}}


def save_bill_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def diff_bills_against_state(
    fetched: list[dict[str, Any]],
    state_path: Path,
    monitored_count: int,
) -> BillTrackerResult:
    state = load_bill_state(state_path)
    bills_state: dict[str, Any] = state.setdefault("bills", {})
    meta: dict[str, Any] = state.setdefault("meta", {})
    is_seed = len(bills_state) == 0
    changes: list[dict[str, Any]] = []
    today = date.today().isoformat()

    for row in fetched:
        bill_id = row["id"].upper()
        prev = bills_state.get(bill_id)
        action_changed = prev is not None and (
            prev.get("latest_action") != row.get("latest_action")
            or prev.get("action_date") != row.get("action_date")
        )

        if prev is None and not is_seed:
            changes.append(
                {
                    **row,
                    "change_type": "new_watchlist",
                    "previous_action": None,
                    "previous_date": None,
                }
            )
        elif action_changed:
            changes.append(
                {
                    **row,
                    "change_type": "status_change",
                    "previous_action": prev.get("latest_action"),
                    "previous_date": prev.get("action_date"),
                }
            )

        if prev is None:
            last_changed = row.get("action_date") or today
        elif action_changed:
            last_changed = today
            meta["last_movement_date"] = today
        else:
            last_changed = prev.get("last_changed", row.get("action_date") or today)

        bills_state[bill_id] = {
            "bill": row.get("bill"),
            "latest_action": row.get("latest_action"),
            "action_date": row.get("action_date"),
            "url": row.get("url"),
            "last_changed": last_changed,
            "last_checked": today,
        }

    if is_seed:
        meta.setdefault("seeded_at", today)
        dates = [b.get("last_changed") for b in bills_state.values() if b.get("last_changed")]
        meta["last_movement_date"] = max(dates) if dates else today
        changes = []
    elif changes:
        meta["last_movement_date"] = today
    elif not meta.get("last_movement_date"):
        dates = [b.get("last_changed") for b in bills_state.values() if b.get("last_changed")]
        meta["last_movement_date"] = max(dates) if dates else today

    save_bill_state(state_path, state)
    last_mv = meta.get("last_movement_date", today)
    quiet = (
        f"No congressional bill movement since {last_mv}. "
        f"({monitored_count} bills monitored.)"
    )
    return BillTrackerResult(
        changes=changes,
        quiet_message=quiet,
        monitored_count=monitored_count,
        movement_count=len(changes),
    )
