"""Market review heuristics for low-probability/high-volume markets."""

from __future__ import annotations

import datetime
from typing import Any

from polymarket_monitor import config


def classify_market(question: str) -> tuple[str, bool, bool]:
    question_lower = question.lower()
    is_low_risk = any(kw in question_lower for kw in config.LOW_INSIDER_RISK_KEYWORDS)
    is_high_risk = any(kw in question_lower for kw in config.INSIDER_RISK_KEYWORDS)
    if is_low_risk and not is_high_risk:
        return "LOW", is_low_risk, is_high_risk
    if is_high_risk:
        return "HIGH", is_low_risk, is_high_risk
    return "MEDIUM", is_low_risk, is_high_risk


def build_alert_reason(risk_level: str, volume: float, prob: float, days_until_close: int) -> str:
    if risk_level == "HIGH" and days_until_close <= config.NEAR_TERM_DAYS:
        return (
            f"Criteria matched: low-probability outcome, ${volume:,.0f} market volume, "
            f"near-term resolution in {days_until_close} days, and event category with "
            "concentrated decision access. Analyst review required."
        )
    if risk_level == "HIGH":
        return (
            f"Criteria matched: low-probability outcome, ${volume:,.0f} market volume, "
            "and event category with concentrated decision access. Longer resolution horizon "
            "lowers urgency; analyst review required."
        )
    if risk_level == "LOW":
        return (
            f"Criteria matched for wash-trading review: low-probability outcome with "
            f"${volume:,.0f} volume in a lower information-asymmetry category. Check for "
            "repeated counterparties, near-zero net exposure, or coordinated timing."
        )
    return (
        f"Criteria matched: ${volume:,.0f} volume on a {prob:.1f}% probability outcome. "
        "Analyst review recommended before drawing conclusions."
    )


def should_flag_market(
    risk_level: str,
    volume: float,
    days_until_close: int,
) -> bool:
    if risk_level == "LOW" and volume < 50_000_000:
        return False
    is_near_term = days_until_close <= config.NEAR_TERM_DAYS
    if not is_near_term and risk_level != "HIGH" and volume < config.HIGH_VOLUME_THRESHOLD:
        return False
    return True


def market_end_date(raw: str) -> tuple[datetime.date | None, int]:
    if not raw:
        return None, 9999
    try:
        parsed = datetime.date.fromisoformat(raw[:10])
        return parsed, (parsed - datetime.date.today()).days
    except Exception:
        return None, 9999


def build_market_signal(market: dict[str, Any], outcome: str, price: Any) -> dict[str, Any] | None:
    volume = float(market.get("volume", 0) or 0)
    prob = float(price) * 100
    if not (prob <= config.LOW_PROB_MAX_PCT and volume >= config.LARGE_TRADE_USD):
        return None

    end_date_raw = market.get("endDate", "")
    end_date_parsed, days_until_close = market_end_date(end_date_raw)
    if end_date_parsed and end_date_parsed < datetime.date.today():
        return None

    risk_level, _, _ = classify_market(market.get("question", ""))
    if not should_flag_market(risk_level, volume, days_until_close):
        return None

    market_id = market.get("id", "")
    return {
        "market_id": market_id,
        "question": market.get("question", ""),
        "outcome": outcome,
        "probability_pct": round(prob, 1),
        "volume_usd": round(volume, 0),
        "url": f"https://polymarket.com/event/{market.get('slug', market_id)}",
        "end_date": end_date_raw[:10] if end_date_raw else "unknown",
        "days_until_close": days_until_close,
        "flagged_date": config.TODAY,
        "insider_risk": risk_level,
        "alert_reason": build_alert_reason(risk_level, volume, prob, days_until_close),
    }

