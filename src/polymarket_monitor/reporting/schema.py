"""Report schema construction helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


@dataclass
class NewsAlert:
    source: str
    title: str
    link: str
    published: str
    pub_date: str
    matched_keywords: list[str]
    summary: str
    score: int
    priority: bool
    watchlist_hit: list[str] = field(default_factory=list)
    also_covered_by: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "NewsAlert":
        return cls(
            source=str(data.get("source", "")),
            title=str(data.get("title", "")),
            link=str(data.get("link", "")),
            published=str(data.get("published", "")),
            pub_date=str(data.get("pub_date", "")),
            matched_keywords=list(data.get("matched_keywords", [])),
            summary=str(data.get("summary", "")),
            score=int(data.get("score", 0) or 0),
            priority=bool(data.get("priority", False)),
            watchlist_hit=list(data.get("watchlist_hit", [])),
            also_covered_by=list(data.get("also_covered_by", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MarketReviewSignal:
    market_id: str
    question: str
    outcome: str
    probability_pct: float
    volume_usd: float
    url: str
    end_date: str
    days_until_close: int
    flagged_date: str
    insider_risk: str
    alert_reason: str

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "MarketReviewSignal":
        return cls(
            market_id=str(data.get("market_id", "")),
            question=str(data.get("question", "")),
            outcome=str(data.get("outcome", "")),
            probability_pct=float(data.get("probability_pct", 0) or 0),
            volume_usd=float(data.get("volume_usd", 0) or 0),
            url=str(data.get("url", "")),
            end_date=str(data.get("end_date", "")),
            days_until_close=int(data.get("days_until_close", 9999) or 9999),
            flagged_date=str(data.get("flagged_date", "")),
            insider_risk=str(data.get("insider_risk", "MEDIUM")),
            alert_reason=str(data.get("alert_reason", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WashTradingReport:
    market_id: str
    question: str
    volume_usd: float
    wash_score: int
    signal_count: int
    signals: list[dict[str, Any]]
    date_analyzed: str
    verdict: str

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "WashTradingReport":
        return cls(
            market_id=str(data.get("market_id", "")),
            question=str(data.get("question", "")),
            volume_usd=float(data.get("volume_usd", 0) or 0),
            wash_score=int(data.get("wash_score", 0) or 0),
            signal_count=int(data.get("signal_count", 0) or 0),
            signals=list(data.get("signals", [])),
            date_analyzed=str(data.get("date_analyzed", "")),
            verdict=str(data.get("verdict", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyReport:
    date: str
    unique_news: int
    suspicious_markets: int
    large_trades: int
    uma_alerts: int
    ofac_new: int
    alerts: list[dict[str, Any]]
    suspicious_market_data: list[dict[str, Any]]
    large_trade_data: list[dict[str, Any]]
    onchain_txs: list[dict[str, Any]]
    uma_governance: list[dict[str, Any]]
    ofac_additions: list[dict[str, Any]]
    bill_updates: list[dict[str, Any]]
    wash_trading_reports: list[dict[str, Any]]
    developing_stories: list[dict[str, Any]]
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_news_alerts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [NewsAlert.from_mapping(item).to_dict() for item in items]


def normalize_market_signals(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [MarketReviewSignal.from_mapping(item).to_dict() for item in items]


def normalize_wash_reports(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [WashTradingReport.from_mapping(item).to_dict() for item in (items or [])]


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
    report = DailyReport(
        date=config.TODAY,
        unique_news=len(news),
        suspicious_markets=len(suspicious_markets),
        large_trades=len(large_trades),
        uma_alerts=len(uma),
        ofac_new=len(ofac),
        alerts=normalize_news_alerts(news),
        suspicious_market_data=normalize_market_signals(suspicious_markets),
        large_trade_data=large_trades,
        onchain_txs=onchain_txs,
        uma_governance=uma,
        ofac_additions=ofac,
        bill_updates=bills,
        wash_trading_reports=normalize_wash_reports(wash_reports),
        developing_stories=developing_stories,
        narrative=narrative,
    )
    return report.to_dict()

