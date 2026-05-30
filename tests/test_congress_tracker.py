import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from polymarket_monitor.detectors.congress_tracker import diff_bills_against_state


class CongressTrackerTests(unittest.TestCase):
    def test_seed_run_returns_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "congress_bill_state.json"
            fetched = [
                {
                    "id": "S4226",
                    "bill": "STOP Corrupt Bets Act",
                    "latest_action": "Referred to Ag",
                    "action_date": "2026-03-26",
                    "url": "https://example.com/s4226",
                }
            ]
            result = diff_bills_against_state(fetched, state_path, monitored_count=1)
            self.assertEqual(result.movement_count, 0)
            self.assertEqual(result.changes, [])
            saved = json.loads(state_path.read_text())
            self.assertIn("S4226", saved["bills"])

    def test_status_change_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "congress_bill_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "bills": {
                            "S4226": {
                                "bill": "STOP Corrupt Bets Act",
                                "latest_action": "Old action",
                                "action_date": "2026-03-20",
                                "url": "https://example.com/s4226",
                                "last_changed": "2026-03-20",
                                "last_checked": "2026-05-29",
                            }
                        },
                        "meta": {"last_movement_date": "2026-03-20"},
                    }
                )
            )
            fetched = [
                {
                    "id": "S4226",
                    "bill": "STOP Corrupt Bets Act",
                    "latest_action": "New action",
                    "action_date": "2026-05-28",
                    "url": "https://example.com/s4226",
                }
            ]
            result = diff_bills_against_state(fetched, state_path, monitored_count=1)
            self.assertEqual(result.movement_count, 1)
            self.assertEqual(result.changes[0]["change_type"], "status_change")
            self.assertEqual(result.changes[0]["previous_action"], "Old action")
            self.assertEqual(result.changes[0]["latest_action"], "New action")

    def test_quiet_message_uses_last_movement_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "congress_bill_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "bills": {
                            "S4226": {
                                "bill": "STOP",
                                "latest_action": "Same",
                                "action_date": "2026-03-26",
                                "url": "https://example.com",
                                "last_changed": "2026-03-26",
                                "last_checked": "2026-05-29",
                            }
                        },
                        "meta": {"last_movement_date": "2026-03-26"},
                    }
                )
            )
            fetched = [
                {
                    "id": "S4226",
                    "bill": "STOP",
                    "latest_action": "Same",
                    "action_date": "2026-03-26",
                    "url": "https://example.com",
                }
            ]
            result = diff_bills_against_state(fetched, state_path, monitored_count=7)
            self.assertEqual(result.movement_count, 0)
            self.assertIn("2026-03-26", result.quiet_message)
            self.assertIn("7 bills monitored", result.quiet_message)

    def test_new_watchlist_bill_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "congress_bill_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "bills": {
                            "S4226": {
                                "bill": "STOP",
                                "latest_action": "Same",
                                "action_date": "2026-03-26",
                                "url": "https://example.com",
                                "last_changed": "2026-03-26",
                                "last_checked": "2026-05-29",
                            }
                        },
                        "meta": {"last_movement_date": "2026-03-26", "seeded_at": "2026-05-29"},
                    }
                )
            )
            fetched = [
                {
                    "id": "S4226",
                    "bill": "STOP",
                    "latest_action": "Same",
                    "action_date": "2026-03-26",
                    "url": "https://example.com",
                },
                {
                    "id": "S4060",
                    "bill": "Prediction Markets Security and Integrity Act",
                    "latest_action": "Referred to Judiciary",
                    "action_date": "2026-03-11",
                    "url": "https://example.com/s4060",
                },
            ]
            result = diff_bills_against_state(fetched, state_path, monitored_count=2)
            self.assertEqual(result.movement_count, 1)
            self.assertEqual(result.changes[0]["change_type"], "new_watchlist")
            self.assertEqual(result.changes[0]["id"], "S4060")


if __name__ == "__main__":
    unittest.main()
