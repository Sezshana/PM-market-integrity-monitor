"""Polymarket Gamma and CLOB clients."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from polymarket_monitor import config
from polymarket_monitor.clients.rss import check_watchlist
from polymarket_monitor.detectors.market_review import build_market_signal
from polymarket_monitor.source_status import STATUS_FAILED, STATUS_OK, get_source_status, mark_source

logger = logging.getLogger(__name__)


def fetch_polymarket_suspicious_trades() -> list[dict[str, Any]]:
    flagged = []
    try:
        resp = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"active": "true", "closed": "false", "limit": 100, "order": "volume", "ascending": "false"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code != 200:
            mark_source("Gamma API", STATUS_FAILED, detail=f"HTTP {resp.status_code}", records=0)
            return []
        markets = resp.json()
        for market in markets[:50]:
            outcomes = market.get("outcomes", "[]")
            prices = market.get("outcomePrices", "[]")
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            if isinstance(prices, str):
                prices = json.loads(prices)
            for outcome, price in zip(outcomes, prices):
                try:
                    signal = build_market_signal(market, outcome, price)
                    if signal:
                        flagged.append(signal)
                except Exception:
                    continue
    except Exception as e:
        logger.warning("Polymarket Gamma API failed: %s", e)
        mark_source("Gamma API", STATUS_FAILED, detail=str(e), records=0)
        print(f"  Polymarket API error: {e}")
    flagged = sorted(flagged, key=lambda x: x["volume_usd"], reverse=True)[:10]
    if "Gamma API" not in get_source_status():
        mark_source("Gamma API", STATUS_OK, detail=f"{len(flagged)} markets matched", records=len(flagged))
    print(f"  Suspicious markets: {len(flagged)}")
    return flagged


def fetch_polymarket_recent_large_trades() -> list[dict[str, Any]]:
    flagged = []
    try:
        resp = requests.get(
            "https://clob.polymarket.com/trades",
            params={"limit": 500},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            trades = data if isinstance(data, list) else data.get("data", [])
            for trade in trades:
                size = float(trade.get("size", 0) or 0)
                price = float(trade.get("price", 1) or 1)
                side = trade.get("side", "")
                prob = price * 100 if side == "BUY" else (1 - price) * 100
                if size >= config.LARGE_TRADE_USD and prob <= config.LOW_PROB_MAX_PCT:
                    maker = trade.get("maker_address", "unknown")
                    taker = trade.get("taker_address", "unknown")
                    ts = trade.get("match_time", "") or config.TODAY
                    flagged.append({
                        "maker": maker,
                        "taker": taker,
                        "size_usd": round(size, 0),
                        "prob_pct": round(prob, 1),
                        "side": side,
                        "asset_id": trade.get("asset_id", ""),
                        "timestamp": ts[:10] if len(str(ts)) >= 10 else ts,
                        "wl_maker": check_watchlist(maker),
                        "wl_taker": check_watchlist(taker),
                    })
        else:
            mark_source("CLOB API", STATUS_FAILED, detail=f"HTTP {resp.status_code}", records=0)
        flagged = sorted(flagged, key=lambda x: x["size_usd"], reverse=True)[:10]
    except Exception as e:
        logger.warning("Polymarket CLOB large-trade fetch failed: %s", e)
        mark_source("CLOB API", STATUS_FAILED, detail=str(e), records=0)
        print(f"  CLOB error: {e}")
    if "CLOB API" not in get_source_status():
        mark_source("CLOB API", STATUS_OK, detail=f"{len(flagged)} large trades matched", records=len(flagged))
    print(f"  Large trades: {len(flagged)}")
    return flagged


def fetch_market_trades(market_id: str, limit: int = 500) -> list[dict[str, Any]]:
    try:
        resp = requests.get(
            "https://clob.polymarket.com/trades",
            params={"market": market_id, "limit": limit},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, list) else data.get("data", [])
        mark_source("CLOB API", STATUS_FAILED, detail=f"market trades HTTP {resp.status_code}", records=0)
    except Exception as e:
        logger.warning("Polymarket CLOB market trades failed for %s: %s", market_id, e)
        mark_source("CLOB API", STATUS_FAILED, detail=str(e), records=0)
        print(f"  Wash trading: CLOB error for {market_id}: {e}")
    return []

