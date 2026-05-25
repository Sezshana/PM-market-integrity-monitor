"""
Wash Trading Detection Module for Polymarket OSINT Monitor
Adds to monitor.py — detects coordinated self-trading patterns.

Key signals:
1. Same wallet pair repeatedly trading against each other
2. Net position near zero despite high volume (economic exposure = 0)
3. Volume wildly out of proportion to open interest
4. Shared funding source between counterparties
5. Synchronized timing patterns between linked wallets
"""

import os
import json
import datetime
import requests
from pathlib import Path
from collections import defaultdict

POLYGONSCAN_KEY  = os.environ.get("POLYGONSCAN_KEY", "")
TODAY            = datetime.date.today().isoformat()

# Thresholds
MIN_TRADE_SIZE_USD      = 1_000     # Minimum trade size to analyze
WASH_PAIR_MIN_TRADES    = 3         # Flag wallet pair if they trade against each other 3+ times
NET_POSITION_THRESHOLD  = 0.05      # Flag if net position < 5% of gross volume (near zero)
VOLUME_OI_RATIO         = 10.0      # Flag if volume > 10x open interest
TIMING_WINDOW_SECONDS   = 60        # Flag if opposite trades happen within 60 seconds


def fetch_market_trades(market_id, limit=500):
    """Fetch all trades for a specific Polymarket market from CLOB API."""
    try:
        resp = requests.get(
            "https://clob.polymarket.com/trades",
            params={"market": market_id, "limit": limit},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, list) else data.get("data", [])
    except Exception as e:
        print(f"  Wash trading: CLOB error for {market_id}: {e}")
    return []


def detect_repeated_counterparties(trades):
    """
    Signal 1: Same two wallets trading against each other repeatedly.
    Legitimate traders rarely end up on opposite sides of the same market
    multiple times. Wash traders do this systematically.
    """
    pair_counts = defaultdict(int)
    pair_volume = defaultdict(float)

    for trade in trades:
        maker = trade.get("maker_address", "")
        taker = trade.get("taker_address", "")
        size  = float(trade.get("size", 0) or 0)

        if maker and taker and maker != taker:
            # Sort so A-B and B-A are the same pair
            pair = tuple(sorted([maker, taker]))
            pair_counts[pair] += 1
            pair_volume[pair] += size

    flagged = []
    for pair, count in pair_counts.items():
        if count >= WASH_PAIR_MIN_TRADES:
            flagged.append({
                "wallet_a":    pair[0],
                "wallet_b":    pair[1],
                "trade_count": count,
                "volume_usd":  round(pair_volume[pair], 0),
                "signal":      "REPEATED COUNTERPARTY",
                "explanation": f"These two wallets traded against each other {count} times. Legitimate traders rarely end up as repeated counterparties on the same market.",
                "polygonscan_a": f"https://polygonscan.com/address/{pair[0]}",
                "polygonscan_b": f"https://polygonscan.com/address/{pair[1]}",
            })
    return sorted(flagged, key=lambda x: x["trade_count"], reverse=True)


def detect_near_zero_net_position(trades):
    """
    Signal 2: Wallet has high gross volume but near-zero net position.
    A wash trader who buys and sells equal amounts ends up with no
    actual market exposure — they never had any real conviction.
    """
    wallet_positions = defaultdict(lambda: {"bought": 0.0, "sold": 0.0})

    for trade in trades:
        maker  = trade.get("maker_address", "")
        taker  = trade.get("taker_address", "")
        size   = float(trade.get("size", 0) or 0)
        side   = trade.get("side", "")
        price  = float(trade.get("price", 0.5) or 0.5)

        if side == "BUY":
            wallet_positions[taker]["bought"] += size
            wallet_positions[maker]["sold"]   += size
        elif side == "SELL":
            wallet_positions[taker]["sold"]   += size
            wallet_positions[maker]["bought"] += size

    flagged = []
    for wallet, pos in wallet_positions.items():
        gross  = pos["bought"] + pos["sold"]
        net    = abs(pos["bought"] - pos["sold"])
        if gross < MIN_TRADE_SIZE_USD:
            continue
        ratio = net / gross if gross > 0 else 1.0
        if ratio < NET_POSITION_THRESHOLD:
            flagged.append({
                "wallet":      wallet,
                "gross_volume": round(gross, 0),
                "net_position": round(net, 0),
                "net_ratio":   round(ratio * 100, 1),
                "signal":      "NEAR-ZERO NET POSITION",
                "explanation": f"${gross:,.0f} in gross trading volume but only ${net:,.0f} in net exposure ({ratio*100:.1f}%). Real traders take positions. Wash traders cancel out.",
                "polygonscan": f"https://polygonscan.com/address/{wallet}",
            })
    return sorted(flagged, key=lambda x: x["gross_volume"], reverse=True)[:5]


def detect_synchronized_timing(trades):
    """
    Signal 3: Trades on opposite sides happening within seconds of each other.
    Wash traders often submit buy and sell orders nearly simultaneously.
    """
    flagged_pairs = []
    sorted_trades = sorted(trades, key=lambda x: x.get("match_time", ""))

    for i, trade_a in enumerate(sorted_trades):
        for trade_b in sorted_trades[i+1:i+20]:  # Check next 20 trades
            try:
                time_a = datetime.datetime.fromisoformat(
                    str(trade_a.get("match_time","")).replace("Z","+00:00")
                )
                time_b = datetime.datetime.fromisoformat(
                    str(trade_b.get("match_time","")).replace("Z","+00:00")
                )
                diff = abs((time_b - time_a).total_seconds())
                if diff > TIMING_WINDOW_SECONDS:
                    break

                maker_a = trade_a.get("maker_address","")
                taker_a = trade_a.get("taker_address","")
                maker_b = trade_b.get("maker_address","")
                taker_b = trade_b.get("taker_address","")

                # Check if same wallets appear on opposite sides in both trades
                wallets_a = {maker_a, taker_a}
                wallets_b = {maker_b, taker_b}
                shared    = wallets_a & wallets_b

                side_a = trade_a.get("side","")
                side_b = trade_b.get("side","")

                if shared and side_a != side_b and diff < TIMING_WINDOW_SECONDS:
                    size_a = float(trade_a.get("size",0) or 0)
                    size_b = float(trade_b.get("size",0) or 0)
                    if size_a >= MIN_TRADE_SIZE_USD and size_b >= MIN_TRADE_SIZE_USD:
                        flagged_pairs.append({
                            "wallet":       list(shared)[0],
                            "trade_a_size": round(size_a, 0),
                            "trade_b_size": round(size_b, 0),
                            "seconds_apart": round(diff, 1),
                            "signal":       "SYNCHRONIZED OPPOSITE TRADES",
                            "explanation":  f"Same wallet appeared on both sides of opposite trades {diff:.1f} seconds apart. Coordinated simultaneous buy/sell is a classic wash trading pattern.",
                        })
            except:
                continue

    return flagged_pairs[:5]


def check_shared_funding_source(wallet_a, wallet_b):
    """
    Signal 4: Two counterparty wallets funded from the same source.
    If both wallets received their initial USDC from the same wallet,
    they are very likely controlled by the same person.
    """
    if not POLYGONSCAN_KEY:
        return None

    def get_funding_wallet(address):
        try:
            resp = requests.get("https://api.polygonscan.com/api", params={
                "module":     "account",
                "action":     "tokentx",
                "address":    address,
                "contractaddress": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "sort":       "asc",
                "apikey":     POLYGONSCAN_KEY,
                "offset":     5,
                "page":       1,
            }, timeout=10)
            data = resp.json()
            if data.get("status") == "1" and data.get("result"):
                return data["result"][0].get("from","")
        except:
            pass
        return None

    funder_a = get_funding_wallet(wallet_a)
    funder_b = get_funding_wallet(wallet_b)

    if funder_a and funder_b and funder_a == funder_b:
        return {
            "shared_funder": funder_a,
            "wallet_a":      wallet_a,
            "wallet_b":      wallet_b,
            "signal":        "SHARED FUNDING SOURCE",
            "explanation":   f"Both wallets received their initial USDC from the same address ({funder_a[:16]}...). This strongly suggests they are controlled by the same person.",
            "polygonscan":   f"https://polygonscan.com/address/{funder_a}",
        }
    return None


def analyze_market_for_wash_trading(market_id, market_question, volume_usd):
    """
    Run full wash trading analysis on a specific market.
    Returns a structured wash trading report.
    """
    print(f"  Wash trading analysis: {market_question[:50]}...")

    trades = fetch_market_trades(market_id)
    if not trades:
        return None

    signals = []

    # Signal 1: Repeated counterparties
    repeated = detect_repeated_counterparties(trades)
    if repeated:
        signals.extend(repeated[:3])

    # Signal 2: Near-zero net positions
    near_zero = detect_near_zero_net_position(trades)
    if near_zero:
        signals.extend(near_zero[:3])

    # Signal 3: Synchronized timing
    synchronized = detect_synchronized_timing(trades)
    if synchronized:
        signals.extend(synchronized[:2])

    # Signal 4: Shared funding for top repeated pair
    if repeated and POLYGONSCAN_KEY:
        top_pair = repeated[0]
        funding_check = check_shared_funding_source(
            top_pair["wallet_a"],
            top_pair["wallet_b"]
        )
        if funding_check:
            signals.append(funding_check)

    if not signals:
        return None

    # Calculate overall wash trading score
    score = 0
    for sig in signals:
        signal_type = sig.get("signal","")
        if "SHARED FUNDING" in signal_type:      score += 5
        if "REPEATED COUNTERPARTY" in signal_type: score += 3 * min(sig.get("trade_count",1), 5)
        if "NEAR-ZERO NET" in signal_type:        score += 3
        if "SYNCHRONIZED" in signal_type:         score += 2

    return {
        "market_id":      market_id,
        "question":       market_question,
        "volume_usd":     volume_usd,
        "wash_score":     score,
        "signal_count":   len(signals),
        "signals":        signals,
        "date_analyzed":  TODAY,
        "verdict":        (
            "HIGH WASH TRADING PROBABILITY" if score >= 8 else
            "MODERATE WASH TRADING SIGNALS" if score >= 4 else
            "LOW-LEVEL SIGNALS — MONITOR"
        ),
    }


def run_wash_trading_detection(suspicious_markets):
    """
    Main entry point — analyze all flagged markets for wash trading.
    Called from monitor.py main() after suspicious markets are identified.
    """
    wash_reports = []

    for market in suspicious_markets[:5]:  # Analyze top 5 by volume
        market_id = market.get("market_id","")
        question  = market.get("question","")
        volume    = market.get("volume_usd", 0)

        if not market_id:
            continue

        report = analyze_market_for_wash_trading(market_id, question, volume)
        if report:
            wash_reports.append(report)

    # Save to data folder for tracking
    wash_log_path = Path("data/wash_trading_log.json")
    existing = []
    if wash_log_path.exists():
        try:
            existing = json.loads(wash_log_path.read_text())
        except:
            existing = []

    # Add today's reports, keep last 90 days
    existing.extend(wash_reports)
    existing = [r for r in existing if r.get("date_analyzed","") >= (
        datetime.date.today() - datetime.timedelta(days=90)
    ).isoformat()]
    wash_log_path.write_text(json.dumps(existing, indent=2))

    wash_reports = sorted(wash_reports, key=lambda x: x["wash_score"], reverse=True)
    print(f"  Wash trading reports: {len(wash_reports)} markets analyzed")
    return wash_reports


def format_wash_trading_email_section(wash_reports):
    """
    Format wash trading findings for the email digest.
    Returns plain text section for inclusion in the email body.
    """
    if not wash_reports:
        return ""

    lines = ["WASH TRADING ANALYSIS", "=" * 60]
    lines.append("Markets analyzed for coordinated self-trading patterns.\n")

    for report in wash_reports:
        verdict_color = {
            "HIGH WASH TRADING PROBABILITY":   "⚠⚠⚠",
            "MODERATE WASH TRADING SIGNALS":   "⚠⚠",
            "LOW-LEVEL SIGNALS — MONITOR":     "⚠",
        }.get(report["verdict"], "⚠")

        lines += [
            f"\n{verdict_color} {report['verdict']} (Score: {report['wash_score']})",
            f"Market: {report['question']}",
            f"Volume: ${report['volume_usd']:,.0f}  |  Signals: {report['signal_count']}",
            f"Analyzed: {report['date_analyzed']}",
        ]

        for sig in report["signals"]:
            signal_type = sig.get("signal","")
            lines.append(f"\n  [{signal_type}]")
            lines.append(f"  {sig.get('explanation','')}")

            if "wallet_a" in sig:
                lines.append(f"  Wallet A: {sig['wallet_a']}")
                lines.append(f"  Wallet B: {sig['wallet_b']}")
                if "trade_count" in sig:
                    lines.append(f"  Trades against each other: {sig['trade_count']} | Volume: ${sig.get('volume_usd',0):,.0f}")

            if "wallet" in sig and "gross_volume" in sig:
                lines.append(f"  Wallet: {sig['wallet']}")
                lines.append(f"  Gross volume: ${sig['gross_volume']:,.0f} | Net position: ${sig['net_position']:,.0f} ({sig['net_ratio']}%)")

            if "shared_funder" in sig:
                lines.append(f"  Shared funder: {sig['shared_funder']}")
                lines.append(f"  Polygonscan: {sig.get('polygonscan','')}")

            lines.append(f"  ACTION: Pull full trade history for flagged wallets. Check if same entity controls both sides.")

        lines.append("\n" + "-" * 40)

    return "\n".join(lines)
