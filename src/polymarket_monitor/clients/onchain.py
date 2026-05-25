"""On-chain review signal collection."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import requests

from polymarket_monitor import config
from polymarket_monitor.clients.polygonscan import get_wallet_age, get_wallet_tx_count
from polymarket_monitor.clients.rss import check_watchlist
from polymarket_monitor.source_status import STATUS_FAILED, STATUS_OK, STATUS_SKIPPED, get_source_status, mark_source

logger = logging.getLogger(__name__)


def fetch_onchain_large_txs() -> list[dict[str, Any]]:
    if not config.POLYGONSCAN_KEY:
        print("  On-chain: no POLYGONSCAN_KEY set — add POLYGONSCAN_KEY to GitHub Secrets")
        mark_source("On-chain/Polygonscan", STATUS_SKIPPED, detail="POLYGONSCAN_KEY not configured", records=0)
        return []

    flagged = []
    try:
        resp = requests.get(
            "https://clob.polymarket.com/trades",
            params={"limit": 500},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"  CLOB API error: {resp.status_code}")
            mark_source("On-chain/Polygonscan", STATUS_FAILED, detail=f"CLOB HTTP {resp.status_code}", records=0)
            return []
        data = resp.json()
        trades = data if isinstance(data, list) else data.get("data", [])
        print(f"  CLOB: {len(trades)} recent trades retrieved")

        suspicious_trades = []
        for trade in trades:
            try:
                size = float(trade.get("size", 0) or 0)
                price = float(trade.get("price", 1) or 1)
                side = trade.get("side", "")
                prob = price * 100 if side == "BUY" else (1 - price) * 100
                if size >= config.LARGE_TRADE_USD and prob <= config.LOW_PROB_MAX_PCT:
                    suspicious_trades.append({
                        "maker": trade.get("maker_address", ""),
                        "taker": trade.get("taker_address", ""),
                        "size": round(size, 0),
                        "prob": round(prob, 1),
                        "side": side,
                        "asset_id": trade.get("asset_id", ""),
                        "time": trade.get("match_time", config.TODAY),
                    })
            except Exception:
                continue
        print(f"  CLOB: {len(suspicious_trades)} large low-probability trades matched review criteria")

        checked_wallets = {}
        for trade in suspicious_trades[:10]:
            for wallet in [trade["maker"], trade["taker"]]:
                if not wallet or wallet in checked_wallets:
                    continue
                checked_wallets[wallet] = {
                    "age": get_wallet_age(wallet),
                    "tx_count": get_wallet_tx_count(wallet),
                }

        for trade in suspicious_trades[:10]:
            maker_info = checked_wallets.get(trade["maker"], {})
            taker_info = checked_wallets.get(trade["taker"], {})
            risk_factors = []
            risk_score = 0
            for label, info in [("Maker", maker_info), ("Taker", taker_info)]:
                age = info.get("age")
                txs = info.get("tx_count", 999)
                if age:
                    try:
                        age_date = datetime.date.fromisoformat(age)
                        days_old = (datetime.date.today() - age_date).days
                        if days_old < 30:
                            risk_factors.append(f"{label} wallet only {days_old} days old")
                            risk_score += 4
                        elif days_old < 90:
                            risk_factors.append(f"{label} wallet {days_old} days old")
                            risk_score += 2
                    except Exception:
                        pass
                if txs < 10:
                    risk_factors.append(f"{label} wallet has only {txs} total transactions")
                    risk_score += 2

            watchlist_hits = check_watchlist(trade["maker"] + " " + trade["taker"])
            if watchlist_hits:
                risk_factors.append(f"Watchlist: {', '.join(watchlist_hits)}")
                risk_score += 5
            if trade["prob"] <= 5:
                risk_score += 2

            if risk_score >= 2 or watchlist_hits:
                flagged.append({
                    "maker": trade["maker"],
                    "taker": trade["taker"],
                    "size_usd": trade["size"],
                    "prob_pct": trade["prob"],
                    "side": trade["side"],
                    "asset_id": trade["asset_id"],
                    "timestamp": str(trade["time"])[:10],
                    "risk_score": risk_score,
                    "risk_factors": risk_factors,
                    "wl_maker": check_watchlist(trade["maker"]),
                    "wl_taker": check_watchlist(trade["taker"]),
                    "maker_age": maker_info.get("age", "unknown"),
                    "taker_age": taker_info.get("age", "unknown"),
                    "polygonscan": f"https://polygonscan.com/address/{trade['maker']}",
                    "from_link": f"https://polygonscan.com/address/{trade['maker']}",
                    "watchlist": watchlist_hits,
                })
    except Exception as e:
        logger.warning("On-chain large transaction collection failed: %s", e)
        mark_source("On-chain/Polygonscan", STATUS_FAILED, detail=str(e), records=0)
        print(f"  On-chain error: {e}")

    flagged = sorted(flagged, key=lambda x: x["risk_score"], reverse=True)[:10]
    if "On-chain/Polygonscan" not in get_source_status():
        mark_source("On-chain/Polygonscan", STATUS_OK, detail=f"{len(flagged)} review trades", records=len(flagged))
    print(f"  On-chain risk-flagged trades: {len(flagged)}")
    return flagged

