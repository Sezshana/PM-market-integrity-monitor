import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from polymarket_monitor import config
from polymarket_monitor.detectors.market_review import (
    build_market_signal,
    classify_market,
    should_flag_market,
)


class MarketReviewDetectorTests(unittest.TestCase):
    def test_classify_market_uses_keyword_groups(self):
        self.assertEqual(classify_market("Will the FDA approval happen?")[0], "HIGH")
        self.assertEqual(classify_market("Will Team A win the NBA championship?")[0], "LOW")
        self.assertEqual(classify_market("Will a new prediction market launch?")[0], "MEDIUM")

    def test_low_risk_markets_require_wash_trading_scale_volume(self):
        self.assertFalse(should_flag_market("LOW", 49_999_999, 10))
        self.assertTrue(should_flag_market("LOW", 50_000_000, 10))

    def test_far_future_medium_market_requires_high_volume(self):
        self.assertFalse(should_flag_market("MEDIUM", config.HIGH_VOLUME_THRESHOLD - 1, 999))
        self.assertTrue(should_flag_market("MEDIUM", config.HIGH_VOLUME_THRESHOLD, 999))

    def test_build_market_signal_preserves_report_contract(self):
        market = {
            "id": "abc123",
            "question": "Will the FDA approval happen?",
            "volume": "25000",
            "slug": "fda-approval",
            "endDate": "2999-01-01T00:00:00Z",
        }

        signal = build_market_signal(market, "Yes", "0.12")

        self.assertIsNotNone(signal)
        self.assertEqual(signal["market_id"], "abc123")
        self.assertEqual(signal["probability_pct"], 12.0)
        self.assertEqual(signal["insider_risk"], "HIGH")
        self.assertIn("Criteria matched", signal["alert_reason"])

    def test_build_market_signal_skips_probability_above_threshold(self):
        market = {
            "id": "abc123",
            "question": "Will the FDA approval happen?",
            "volume": "25000",
            "slug": "fda-approval",
            "endDate": "2999-01-01T00:00:00Z",
        }

        self.assertIsNone(build_market_signal(market, "Yes", "0.25"))


if __name__ == "__main__":
    unittest.main()
