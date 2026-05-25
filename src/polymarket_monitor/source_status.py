"""Runtime source coverage status for daily collection."""

from __future__ import annotations

import datetime
from typing import Any

STATUS_OK = "OK"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"

_SOURCE_STATUS: dict[str, dict[str, Any]] = {}


def mark_source(name: str, status: str, *, detail: str = "", records: int | None = None) -> None:
    item: dict[str, Any] = {
        "status": status,
        "detail": detail,
        "updated_at": datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    if records is not None:
        item["records"] = records
    _SOURCE_STATUS[name] = item


def get_source_status() -> dict[str, dict[str, Any]]:
    return dict(_SOURCE_STATUS)


def reset_source_status() -> None:
    _SOURCE_STATUS.clear()

