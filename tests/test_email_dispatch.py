"""Email dispatch deduplication tests."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from polymarket_monitor.reporting import dispatch


class EmailDispatchTests(unittest.TestCase):
    def test_duplicate_send_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "email_dispatch_state.json"
            state.write_text(json.dumps({"eastern_date": dispatch.eastern_today()}))
            skip, reason = dispatch.should_skip_duplicate_send(state)
            self.assertTrue(skip)
            self.assertIn("already sent", reason)

    def test_force_email_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "email_dispatch_state.json"
            state.write_text(json.dumps({"eastern_date": dispatch.eastern_today()}))
            with mock.patch.dict(os.environ, {"FORCE_EMAIL": "true"}, clear=False):
                skip, _ = dispatch.should_skip_duplicate_send(state)
            self.assertFalse(skip)

    def test_mark_email_sent_writes_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "email_dispatch_state.json"
            dispatch.mark_email_sent("Test subject", state)
            payload = json.loads(state.read_text())
            self.assertEqual(payload["eastern_date"], dispatch.eastern_today())
            self.assertEqual(payload["subject"], "Test subject")


if __name__ == "__main__":
    unittest.main()
