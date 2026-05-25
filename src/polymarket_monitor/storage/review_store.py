"""SQLite storage for analyst review state."""

from __future__ import annotations

import datetime
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reviewed_alerts (
    alert_id TEXT PRIMARY KEY,
    signal_type TEXT NOT NULL,
    status TEXT NOT NULL,
    question TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    false_positive_reason TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reviewed_alerts_status
ON reviewed_alerts(status);

CREATE INDEX IF NOT EXISTS idx_reviewed_alerts_signal_type
ON reviewed_alerts(signal_type);
"""

VALID_STATUSES = {"new", "reviewed", "dismissed", "escalated"}


@dataclass
class ReviewedAlert:
    alert_id: str
    signal_type: str
    status: str = "new"
    question: str = ""
    source_url: str = ""
    notes: str = ""
    false_positive_reason: str = ""
    payload: dict[str, Any] | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_row(self) -> dict[str, Any]:
        now = datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        created = self.created_at or now
        updated = self.updated_at or now
        return {
            "alert_id": self.alert_id,
            "signal_type": self.signal_type,
            "status": self.status,
            "question": self.question,
            "source_url": self.source_url,
            "notes": self.notes,
            "false_positive_reason": self.false_positive_reason,
            "payload_json": json.dumps(self.payload or {}, sort_keys=True),
            "created_at": created,
            "updated_at": updated,
        }


class ReviewStore:
    def __init__(self, db_path: str | Path = "data/reviewed_alerts.sqlite3") -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def upsert_alert(self, alert: ReviewedAlert) -> None:
        if alert.status not in VALID_STATUSES:
            raise ValueError(f"Invalid alert status: {alert.status}")
        row = alert.to_row()
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                """
                INSERT INTO reviewed_alerts (
                    alert_id, signal_type, status, question, source_url, notes,
                    false_positive_reason, payload_json, created_at, updated_at
                )
                VALUES (
                    :alert_id, :signal_type, :status, :question, :source_url, :notes,
                    :false_positive_reason, :payload_json, :created_at, :updated_at
                )
                ON CONFLICT(alert_id) DO UPDATE SET
                    signal_type = excluded.signal_type,
                    status = excluded.status,
                    question = excluded.question,
                    source_url = excluded.source_url,
                    notes = excluded.notes,
                    false_positive_reason = excluded.false_positive_reason,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                row,
            )

    def update_status(
        self,
        alert_id: str,
        status: str,
        *,
        notes: str | None = None,
        false_positive_reason: str | None = None,
    ) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid alert status: {status}")
        now = datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        updates = ["status = ?", "updated_at = ?"]
        values: list[Any] = [status, now]
        if notes is not None:
            updates.append("notes = ?")
            values.append(notes)
        if false_positive_reason is not None:
            updates.append("false_positive_reason = ?")
            values.append(false_positive_reason)
        values.append(alert_id)

        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                f"UPDATE reviewed_alerts SET {', '.join(updates)} WHERE alert_id = ?",
                values,
            )

    def list_alerts(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM reviewed_alerts"
        values: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            values = (status,)
        query += " ORDER BY updated_at DESC"
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            rows = conn.execute(query, values).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json") or "{}")
            result.append(item)
        return result

