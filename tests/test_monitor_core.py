import tempfile
import unittest
from pathlib import Path

import monitor
from wash_trading_module import (
    detect_near_zero_net_position,
    detect_repeated_counterparties,
)


class WatchlistParsingTests(unittest.TestCase):
    def test_load_watchlist_parses_sections_and_normalizes_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            watchlist = Path(tmpdir) / "watchlist.txt"
            watchlist.write_text(
                "\n".join(
                    [
                        "# comment",
                        "[keywords]",
                        "Prediction Market Probe",
                        "",
                        "[wallets]",
                        "0xABCDEF",
                        "[handles]",
                        "@marketwatcher",
                    ]
                )
            )

            parsed = monitor.load_watchlist(watchlist)

        self.assertEqual(parsed["keywords"], ["prediction market probe"])
        self.assertEqual(parsed["wallets"], ["0xabcdef"])
        self.assertEqual(parsed["handles"], ["marketwatcher"])


class ArticleScoringTests(unittest.TestCase):
    def test_score_article_uses_priority_weights(self):
        score = monitor.score_article(
            "CFTC enforcement action targets prediction market manipulation",
            "The probe references Polymarket and alleged insider trading.",
            ["polymarket"],
        )

        self.assertGreaterEqual(score, 10)

    def test_deduplicate_keeps_highest_priority_source(self):
        hits = [
            {
                "source": "Decrypt",
                "title": "CFTC opens probe into prediction market trading",
            },
            {
                "source": "CFTC Press Releases",
                "title": "Prediction market trading probe opened by CFTC",
            },
        ]

        deduped = monitor.deduplicate(hits)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["source"], "CFTC Press Releases")
        self.assertEqual(deduped[0]["also_covered_by"], ["Decrypt"])


class WashTradingSignalTests(unittest.TestCase):
    def test_detect_repeated_counterparties_flags_repeated_pair(self):
        trades = [
            {"maker_address": "0xaaa", "taker_address": "0xbbb", "size": "1000"},
            {"maker_address": "0xbbb", "taker_address": "0xaaa", "size": "1500"},
            {"maker_address": "0xaaa", "taker_address": "0xbbb", "size": "2000"},
        ]

        signals = detect_repeated_counterparties(trades)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["trade_count"], 3)
        self.assertIn("Repeated counterparty pattern observed", signals[0]["explanation"])

    def test_detect_near_zero_net_position_flags_low_net_exposure(self):
        trades = [
            {
                "maker_address": "0xmaker",
                "taker_address": "0xwallet",
                "size": "1000",
                "side": "BUY",
            },
            {
                "maker_address": "0xmaker",
                "taker_address": "0xwallet",
                "size": "980",
                "side": "SELL",
            },
        ]

        signals = detect_near_zero_net_position(trades)

        self.assertTrue(any(signal["wallet"] == "0xwallet" for signal in signals))
        wallet_signal = next(signal for signal in signals if signal["wallet"] == "0xwallet")
        self.assertLess(wallet_signal["net_ratio"], 5)
        self.assertIn("Near-zero net exposure observed", wallet_signal["explanation"])


if __name__ == "__main__":
    unittest.main()
