import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

# Keep these contract tests offline; they exercise report/dashboard shape only.
sys.modules.setdefault(
    "bs4",
    types.SimpleNamespace(BeautifulSoup=lambda html, parser: types.SimpleNamespace(get_text=lambda: html or "")),
)
sys.modules.setdefault("feedparser", types.SimpleNamespace(parse=lambda url: types.SimpleNamespace(entries=[])))

import monitor

from polymarket_monitor.detectors.congress_tracker import BillTrackerResult


REPORT_TOP_LEVEL_FIELDS = {
    "date",
    "unique_news",
    "suspicious_markets",
    "large_trades",
    "uma_alerts",
    "ofac_new",
    "alerts",
    "suspicious_market_data",
    "large_trade_data",
    "onchain_txs",
    "uma_governance",
    "ofac_additions",
    "bill_updates",
    "bill_tracker",
    "wash_trading_reports",
    "developing_stories",
    "narrative",
    "source_coverage",
}

MARKET_FIELDS = {
    "market_id",
    "question",
    "outcome",
    "probability_pct",
    "volume_usd",
    "url",
    "end_date",
    "days_until_close",
    "flagged_date",
    "insider_risk",
    "alert_reason",
}

NEWS_FIELDS = {
    "source",
    "title",
    "link",
    "published",
    "pub_date",
    "matched_keywords",
    "summary",
    "score",
    "priority",
    "watchlist_hit",
    "also_covered_by",
}

WASH_REPORT_FIELDS = {
    "market_id",
    "question",
    "volume_usd",
    "wash_score",
    "signal_count",
    "signals",
    "date_analyzed",
    "verdict",
}

DASHBOARD_REPORT_FIELD_REFERENCES = {
    "date",
    "alerts",
    "suspicious_market_data",
    "bill_updates",
    "wash_trading_reports",
    "developing_stories",
    "narrative",
    "priority",
    "source",
    "pub_date",
    "title",
    "summary",
    "link",
    "question",
    "volume_usd",
    "probability_pct",
    "end_date",
    "url",
    "insider_risk",
    "wash_score",
    "signal_count",
}

DASHBOARD_AGGREGATE_FIELD_REFERENCES = {
    "total_wallets_tracked",
    "recurring_wallets",
    "total_markets_tracked",
    "persistent_markets",
    "summary_stats",
    "total_alerts_30d",
    "wallets_with_ofac",
    "high_risk_wallets",
    "win_rate_alerts",
    "daily_trend",
    "top_keywords",
    "top_sources",
}


class ReportSchemaContractTests(unittest.TestCase):
    def test_save_report_writes_expected_json_contract(self):
        news = [
            {
                "source": "CFTC Press Releases",
                "title": "Prediction market enforcement update",
                "link": "https://example.test/news",
                "published": "Mon, 25 May 2026 12:00:00 GMT",
                "pub_date": "May 25, 2026",
                "matched_keywords": ["polymarket"],
                "summary": "Short summary.",
                "score": 4,
                "priority": True,
                "watchlist_hit": [],
                "also_covered_by": [],
            }
        ]
        markets = [
            {
                "market_id": "123",
                "question": "Will a review event happen?",
                "outcome": "Yes",
                "probability_pct": 12.5,
                "volume_usd": 25000,
                "url": "https://polymarket.com/event/123",
                "end_date": "2026-06-01",
                "days_until_close": 7,
                "flagged_date": monitor.TODAY,
                "insider_risk": "MEDIUM",
                "alert_reason": "Criteria matched: sample.",
            }
        ]
        wash_reports = [
            {
                "market_id": "123",
                "question": "Will a review event happen?",
                "volume_usd": 25000,
                "wash_score": 4,
                "signal_count": 1,
                "signals": [{"signal": "REPEATED COUNTERPARTY"}],
                "date_analyzed": monitor.TODAY,
                "verdict": "MODERATE WASH-TRADING REVIEW SIGNALS",
            }
        ]

        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                Path("output").mkdir()
                Path("data").mkdir()
                monitor.save_report(
                    news=news,
                    suspicious_markets=markets,
                    large_trades=[],
                    onchain_txs=[],
                    uma=[],
                    ofac=[],
                    bill_tracker=BillTrackerResult(
                        quiet_message="No congressional bill movement since 2026-03-26. (7 bills monitored.)",
                        monitored_count=7,
                    ),
                    win_alerts=[],
                    weekly=None,
                    narrative="Criteria matched sample narrative.",
                    developing_stories=[],
                    wash_reports=wash_reports,
                )
                report_path = Path("output") / f"report_{monitor.TODAY}.json"
                report = json.loads(report_path.read_text())
            finally:
                os.chdir(old_cwd)

        self.assertTrue(REPORT_TOP_LEVEL_FIELDS.issubset(report.keys()))
        self.assertTrue(NEWS_FIELDS.issubset(report["alerts"][0].keys()))
        self.assertTrue(MARKET_FIELDS.issubset(report["suspicious_market_data"][0].keys()))
        self.assertTrue(WASH_REPORT_FIELDS.issubset(report["wash_trading_reports"][0].keys()))
        self.assertIn("source_coverage", report)


class DashboardContractTests(unittest.TestCase):
    def test_dashboard_references_expected_report_and_aggregate_fields(self):
        dashboard = Path("dashboard.html").read_text()

        missing_report_fields = [
            field for field in sorted(DASHBOARD_REPORT_FIELD_REFERENCES)
            if field not in dashboard
        ]
        missing_aggregate_fields = [
            field for field in sorted(DASHBOARD_AGGREGATE_FIELD_REFERENCES)
            if field not in dashboard
        ]

        self.assertEqual(missing_report_fields, [])
        self.assertEqual(missing_aggregate_fields, [])

    def test_dashboard_escapes_attribute_quotes_and_sanitizes_links(self):
        dashboard = Path("dashboard.html").read_text()

        self.assertIn("function safeUrl(url)", dashboard)
        self.assertIn("parsed.protocol === 'https:' || parsed.protocol === 'http:'", dashboard)
        self.assertIn("rel=\"noopener noreferrer\"", dashboard)
        self.assertIn(".replace(/\"/g,'&quot;')", dashboard)
        self.assertIn(".replace(/'/g,'&#39;')", dashboard)
        self.assertNotIn('href="${esc(', dashboard)


if __name__ == "__main__":
    unittest.main()
