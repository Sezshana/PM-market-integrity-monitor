import tempfile
import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from polymarket_monitor.reporting.schema import (
    DailyReport,
    MarketReviewSignal,
    NewsAlert,
    WashTradingReport,
    build_daily_report,
)
from polymarket_monitor.storage.review_store import ReviewStore, ReviewedAlert
from polymarket_monitor.storage.json_store import load_json, save_json


class ReportSchemaTests(unittest.TestCase):
    def test_typed_schema_normalizes_core_report_sections(self):
        news = NewsAlert.from_mapping({
            "source": "CoinDesk",
            "title": "Example",
            "link": "https://example.test",
            "published": "raw",
            "pub_date": "May 25, 2026",
            "matched_keywords": ["polymarket"],
            "summary": "summary",
            "score": "4",
            "priority": True,
        })
        market = MarketReviewSignal.from_mapping({
            "market_id": "m1",
            "question": "Question?",
            "outcome": "Yes",
            "probability_pct": "12.5",
            "volume_usd": "10000",
            "url": "https://polymarket.com/event/m1",
            "end_date": "2999-01-01",
            "days_until_close": "30",
            "flagged_date": "2026-05-25",
            "insider_risk": "MEDIUM",
            "alert_reason": "Criteria matched.",
        })
        wash = WashTradingReport.from_mapping({
            "market_id": "m1",
            "question": "Question?",
            "volume_usd": "10000",
            "wash_score": "4",
            "signal_count": "1",
            "signals": [{"signal": "REPEATED COUNTERPARTY"}],
            "date_analyzed": "2026-05-25",
            "verdict": "MODERATE WASH-TRADING REVIEW SIGNALS",
        })

        self.assertEqual(news.score, 4)
        self.assertEqual(market.probability_pct, 12.5)
        self.assertEqual(wash.signal_count, 1)

    def test_build_daily_report_returns_stable_dict_contract(self):
        report = build_daily_report(
            news=[],
            suspicious_markets=[],
            large_trades=[],
            onchain_txs=[],
            uma=[],
            ofac=[],
            bills=[],
            narrative="No criteria matched.",
            developing_stories=[],
            wash_reports=[],
            source_coverage={"RSS": {"status": "OK"}},
        )

        daily_report = DailyReport(**report)
        self.assertEqual(daily_report.unique_news, 0)
        self.assertEqual(daily_report.narrative, "No criteria matched.")
        self.assertEqual(daily_report.source_coverage["RSS"]["status"], "OK")


class ReviewStoreTests(unittest.TestCase):
    def test_json_store_loads_defaults_and_round_trips_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            self.assertEqual(load_json(path, {"missing": True}), {"missing": True})

            save_json(path, {"ok": True, "count": 2})

            self.assertEqual(load_json(path, {}), {"ok": True, "count": 2})

    def test_review_store_upserts_and_updates_alert_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReviewStore(Path(tmpdir) / "reviewed_alerts.sqlite3")
            store.initialize()
            store.upsert_alert(
                ReviewedAlert(
                    alert_id="market:m1",
                    signal_type="market_review",
                    question="Question?",
                    source_url="https://polymarket.com/event/m1",
                    payload={"market_id": "m1"},
                )
            )
            store.update_status(
                "market:m1",
                "dismissed",
                notes="Reviewed with public-news context.",
                false_positive_reason="Public information explained movement.",
            )

            alerts = store.list_alerts()

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["status"], "dismissed")
        self.assertEqual(alerts[0]["payload"], {"market_id": "m1"})
        self.assertIn("public-news", alerts[0]["notes"])

    def test_review_store_rejects_invalid_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReviewStore(Path(tmpdir) / "reviewed_alerts.sqlite3")
            with self.assertRaises(ValueError):
                store.upsert_alert(
                    ReviewedAlert(
                        alert_id="market:m1",
                        signal_type="market_review",
                        status="unknown",
                    )
                )


if __name__ == "__main__":
    unittest.main()
