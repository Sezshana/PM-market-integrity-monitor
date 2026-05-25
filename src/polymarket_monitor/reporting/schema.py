"""Report schema construction helpers."""

from __future__ import annotations

from typing import Any

from polymarket_monitor import config


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
    "wash_trading_reports",
    "developing_stories",
    "narrative",
}


def build_daily_report(
    news: list[dict[str, Any]],
    suspicious_markets: list[dict[str, Any]],
    large_trades: list[dict[str, Any]],
    onchain_txs: list[dict[str, Any]],
    uma: list[dict[str, Any]],
    ofac: list[dict[str, Any]],
    bills: list[dict[str, Any]],
    narrative: str,
    developing_stories: list[dict[str, Any]],
    wash_reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "date": config.TODAY,
        "unique_news": len(news),
        "suspicious_markets": len(suspicious_markets),
        "large_trades": len(large_trades),
        "uma_alerts": len(uma),
        "ofac_new": len(ofac),
        "alerts": news,
        "suspicious_market_data": suspicious_markets,
        "large_trade_data": large_trades,
        "onchain_txs": onchain_txs,
        "uma_governance": uma,
        "ofac_additions": ofac,
        "bill_updates": bills,
        "wash_trading_reports": wash_reports or [],
        "developing_stories": developing_stories,
        "narrative": narrative,
    }

