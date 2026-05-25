"""Wash-trading review signals."""

from __future__ import annotations

import datetime
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from polymarket_monitor import config
from polymarket_monitor.clients.polygonscan import get_funding_wallet
from polymarket_monitor.clients.polymarket import fetch_market_trades

MIN_TRADE_SIZE_USD = 1_000
WASH_PAIR_MIN_TRADES = 3
NET_POSITION_THRESHOLD = 0.05
VOLUME_OI_RATIO = 10.0
TIMING_WINDOW_SECONDS = 60


def detect_repeated_counterparties(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pair_counts = defaultdict(int)
    pair_volume = defaultdict(float)
    for trade in trades:
        maker = trade.get("maker_address", "")
        taker = trade.get("taker_address", "")
        size = float(trade.get("size", 0) or 0)
        if maker and taker and maker != taker:
            pair = tuple(sorted([maker, taker]))
            pair_counts[pair] += 1
            pair_volume[pair] += size

    flagged = []
    for pair, count in pair_counts.items():
        if count >= WASH_PAIR_MIN_TRADES:
            flagged.append({
                "wallet_a": pair[0],
                "wallet_b": pair[1],
                "trade_count": count,
                "volume_usd": round(pair_volume[pair], 0),
                "signal": "REPEATED COUNTERPARTY",
                "explanation": f"These two wallets traded against each other {count} times on the same market. Repeated counterparty pattern observed; analyst review required.",
                "polygonscan_a": f"https://polygonscan.com/address/{pair[0]}",
                "polygonscan_b": f"https://polygonscan.com/address/{pair[1]}",
            })
    return sorted(flagged, key=lambda x: x["trade_count"], reverse=True)


def detect_near_zero_net_position(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wallet_positions = defaultdict(lambda: {"bought": 0.0, "sold": 0.0})
    for trade in trades:
        maker = trade.get("maker_address", "")
        taker = trade.get("taker_address", "")
        size = float(trade.get("size", 0) or 0)
        side = trade.get("side", "")
        if side == "BUY":
            wallet_positions[taker]["bought"] += size
            wallet_positions[maker]["sold"] += size
        elif side == "SELL":
            wallet_positions[taker]["sold"] += size
            wallet_positions[maker]["bought"] += size

    flagged = []
    for wallet, pos in wallet_positions.items():
        gross = pos["bought"] + pos["sold"]
        net = abs(pos["bought"] - pos["sold"])
        if gross < MIN_TRADE_SIZE_USD:
            continue
        ratio = net / gross if gross > 0 else 1.0
        if ratio < NET_POSITION_THRESHOLD:
            flagged.append({
                "wallet": wallet,
                "gross_volume": round(gross, 0),
                "net_position": round(net, 0),
                "net_ratio": round(ratio * 100, 1),
                "signal": "NEAR-ZERO NET POSITION",
                "explanation": f"${gross:,.0f} in gross trading volume but only ${net:,.0f} in net exposure ({ratio*100:.1f}%). Near-zero net exposure observed; analyst review required.",
                "polygonscan": f"https://polygonscan.com/address/{wallet}",
            })
    return sorted(flagged, key=lambda x: x["gross_volume"], reverse=True)[:5]


def detect_synchronized_timing(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flagged_pairs = []
    sorted_trades = sorted(trades, key=lambda x: x.get("match_time", ""))
    for i, trade_a in enumerate(sorted_trades):
        for trade_b in sorted_trades[i + 1:i + 20]:
            try:
                time_a = datetime.datetime.fromisoformat(str(trade_a.get("match_time", "")).replace("Z", "+00:00"))
                time_b = datetime.datetime.fromisoformat(str(trade_b.get("match_time", "")).replace("Z", "+00:00"))
                diff = abs((time_b - time_a).total_seconds())
                if diff > TIMING_WINDOW_SECONDS:
                    break
                wallets_a = {trade_a.get("maker_address", ""), trade_a.get("taker_address", "")}
                wallets_b = {trade_b.get("maker_address", ""), trade_b.get("taker_address", "")}
                shared = wallets_a & wallets_b
                if shared and trade_a.get("side", "") != trade_b.get("side", "") and diff < TIMING_WINDOW_SECONDS:
                    size_a = float(trade_a.get("size", 0) or 0)
                    size_b = float(trade_b.get("size", 0) or 0)
                    if size_a >= MIN_TRADE_SIZE_USD and size_b >= MIN_TRADE_SIZE_USD:
                        flagged_pairs.append({
                            "wallet": list(shared)[0],
                            "trade_a_size": round(size_a, 0),
                            "trade_b_size": round(size_b, 0),
                            "seconds_apart": round(diff, 1),
                            "signal": "SYNCHRONIZED OPPOSITE TRADES",
                            "explanation": f"Same wallet appeared on both sides of opposite trades {diff:.1f} seconds apart. Synchronized opposite-side timing observed; analyst review required.",
                        })
            except Exception:
                continue
    return flagged_pairs[:5]


def check_shared_funding_source(wallet_a: str, wallet_b: str) -> dict[str, Any] | None:
    if not config.POLYGONSCAN_KEY:
        return None
    funder_a = get_funding_wallet(wallet_a)
    funder_b = get_funding_wallet(wallet_b)
    if funder_a and funder_b and funder_a == funder_b:
        return {
            "shared_funder": funder_a,
            "wallet_a": wallet_a,
            "wallet_b": wallet_b,
            "signal": "SHARED FUNDING SOURCE",
            "explanation": f"Both wallets received their initial USDC from the same address ({funder_a[:16]}...). Shared funder observed; analyst review required before inferring common control.",
            "polygonscan": f"https://polygonscan.com/address/{funder_a}",
        }
    return None


def analyze_market_for_wash_trading(market_id: str, market_question: str, volume_usd: float) -> dict[str, Any] | None:
    print(f"  Wash trading analysis: {market_question[:50]}...")
    trades = fetch_market_trades(market_id)
    if not trades:
        return None

    signals = []
    repeated = detect_repeated_counterparties(trades)
    if repeated:
        signals.extend(repeated[:3])
    near_zero = detect_near_zero_net_position(trades)
    if near_zero:
        signals.extend(near_zero[:3])
    synchronized = detect_synchronized_timing(trades)
    if synchronized:
        signals.extend(synchronized[:2])
    if repeated and config.POLYGONSCAN_KEY:
        funding_check = check_shared_funding_source(repeated[0]["wallet_a"], repeated[0]["wallet_b"])
        if funding_check:
            signals.append(funding_check)
    if not signals:
        return None

    score = 0
    for sig in signals:
        signal_type = sig.get("signal", "")
        if "SHARED FUNDING" in signal_type:
            score += 5
        if "REPEATED COUNTERPARTY" in signal_type:
            score += 3 * min(sig.get("trade_count", 1), 5)
        if "NEAR-ZERO NET" in signal_type:
            score += 3
        if "SYNCHRONIZED" in signal_type:
            score += 2

    return {
        "market_id": market_id,
        "question": market_question,
        "volume_usd": volume_usd,
        "wash_score": score,
        "signal_count": len(signals),
        "signals": signals,
        "date_analyzed": config.TODAY,
        "verdict": (
            "MULTIPLE WASH-TRADING REVIEW SIGNALS" if score >= 8 else
            "MODERATE WASH-TRADING REVIEW SIGNALS" if score >= 4 else
            "LOW-LEVEL SIGNALS — MONITOR"
        ),
    }


def run_wash_trading_detection(suspicious_markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wash_reports = []
    for market in suspicious_markets[:5]:
        market_id = market.get("market_id", "")
        if not market_id:
            continue
        report = analyze_market_for_wash_trading(market_id, market.get("question", ""), market.get("volume_usd", 0))
        if report:
            wash_reports.append(report)

    wash_log_path = Path("data/wash_trading_log.json")
    existing = []
    if wash_log_path.exists():
        try:
            existing = json.loads(wash_log_path.read_text())
        except Exception:
            existing = []
    existing.extend(wash_reports)
    cutoff = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
    existing = [r for r in existing if r.get("date_analyzed", "") >= cutoff]
    wash_log_path.write_text(json.dumps(existing, indent=2))

    wash_reports = sorted(wash_reports, key=lambda x: x["wash_score"], reverse=True)
    print(f"  Wash trading reports: {len(wash_reports)} markets analyzed")
    return wash_reports


def format_wash_trading_email_section(wash_reports: list[dict[str, Any]]) -> str:
    if not wash_reports:
        return ""
    lines = ["WASH TRADING ANALYSIS", "=" * 60]
    lines.append("Markets analyzed for coordinated self-trading patterns.\n")
    for report in wash_reports:
        verdict_color = {
            "MULTIPLE WASH-TRADING REVIEW SIGNALS": "⚠⚠⚠",
            "MODERATE WASH-TRADING REVIEW SIGNALS": "⚠⚠",
            "LOW-LEVEL SIGNALS — MONITOR": "⚠",
        }.get(report["verdict"], "⚠")
        lines += [
            f"\n{verdict_color} {report['verdict']} (Score: {report['wash_score']})",
            f"Market: {report['question']}",
            f"Volume: ${report['volume_usd']:,.0f}  |  Signals: {report['signal_count']}",
            f"Analyzed: {report['date_analyzed']}",
        ]
        for sig in report["signals"]:
            signal_type = sig.get("signal", "")
            lines.append(f"\n  [{signal_type}]")
            lines.append(f"  {sig.get('explanation', '')}")
            if "wallet_a" in sig:
                lines.append(f"  Wallet A: {sig['wallet_a']}")
                lines.append(f"  Wallet B: {sig['wallet_b']}")
                if "trade_count" in sig:
                    lines.append(f"  Trades: {sig['trade_count']}  |  Volume: ${sig.get('volume_usd', 0):,.0f}")
            elif "wallet" in sig:
                lines.append(f"  Wallet: {sig['wallet']}")
                if "gross_volume" in sig:
                    lines.append(f"  Gross volume: ${sig['gross_volume']:,.0f}  |  Net position: ${sig['net_position']:,.0f}")
            if sig.get("polygonscan"):
                lines.append(f"  Polygonscan: {sig['polygonscan']}")
        lines.append("")
    return "\n".join(lines)

