"""
Polymarket Intelligence Aggregator
Runs after daily monitor — builds persistent intelligence database
from daily JSON reports. Surfaces patterns invisible in single-day views.
"""

import os
import json
import datetime
import sys
from pathlib import Path
from collections import defaultdict

SRC_DIR = Path(__file__).resolve().parent / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

TODAY     = datetime.date.today().isoformat()
OUTPUT    = Path("output")
DATA      = Path("data")
DATA.mkdir(exist_ok=True)

# Persistent intelligence files
WALLET_REGISTRY   = DATA / "wallet_registry.json"
MARKET_HISTORY    = DATA / "market_history.json"
AGGREGATE_INTEL   = DATA / "aggregate_intelligence.json"

RETENTION_DAYS = 90  # Keep 90 days of history


# ════════════════════════════════════════════════════════════
# LOAD / SAVE HELPERS
# ════════════════════════════════════════════════════════════

def load_json(path, default):
    if Path(path).exists():
        try:
            return json.loads(Path(path).read_text())
        except:
            return default
    return default

def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2))

def cutoff_date():
    return (datetime.date.today() - datetime.timedelta(days=RETENTION_DAYS)).isoformat()


# ════════════════════════════════════════════════════════════
# WALLET REGISTRY
# ════════════════════════════════════════════════════════════

def update_wallet_registry(report):
    """
    Extract all wallet addresses from today's report and update
    the persistent registry with appearance counts, signals, and history.
    """
    registry = load_json(WALLET_REGISTRY, {})

    def register_wallet(address, source, signal, market=None, amount=None, risk_score=None):
        if not address or len(address) < 10:
            return
        address = address.lower()
        if address not in registry:
            registry[address] = {
                "first_seen":     TODAY,
                "last_seen":      TODAY,
                "appearance_count": 0,
                "sources":        [],
                "signals":        [],
                "markets":        [],
                "total_flagged_amount": 0,
                "max_risk_score": 0,
                "risk_history":   [],
                "ofac_match":     False,
                "watchlist_hit":  False,
            }

        w = registry[address]
        w["last_seen"]        = TODAY
        w["appearance_count"] += 1

        if source not in w["sources"]:
            w["sources"].append(source)
        if signal not in w["signals"]:
            w["signals"].append(signal)
        if market and market not in w["markets"]:
            w["markets"].append(market[:80])
        if amount:
            w["total_flagged_amount"] += float(amount)
        if risk_score:
            w["max_risk_score"] = max(w["max_risk_score"], int(risk_score))
            w["risk_history"].append({"date": TODAY, "score": risk_score})
            # Keep last 30 risk scores
            w["risk_history"] = w["risk_history"][-30:]

    # Extract from on-chain flagged trades
    for tx in report.get("onchain_txs", []):
        register_wallet(
            tx.get("from",""), "on_chain", "large_trade",
            amount=tx.get("size_usd", tx.get("value_usdc", 0)),
            risk_score=tx.get("risk_score", 1)
        )
        register_wallet(
            tx.get("taker","") or tx.get("to",""), "on_chain", "large_trade_counterparty"
        )
        if tx.get("watchlist"):
            addr = tx.get("from","").lower() or tx.get("maker","").lower()
            if addr in registry:
                registry[addr]["watchlist_hit"] = True

    # Extract from wash trading signals
    for wt in report.get("wash_trading_reports", []):
        for sig in wt.get("signals", []):
            if "wallet_a" in sig:
                register_wallet(sig["wallet_a"], "wash_trading",
                    sig.get("signal","wash_trade"),
                    market=wt.get("question",""),
                    amount=sig.get("volume_usd", 0))
                register_wallet(sig["wallet_b"], "wash_trading",
                    sig.get("signal","wash_trade_counterparty"),
                    market=wt.get("question",""))
            if "wallet" in sig and "gross_volume" in sig:
                register_wallet(sig["wallet"], "wash_trading",
                    "near_zero_net_position",
                    market=wt.get("question",""),
                    amount=sig.get("gross_volume",0))

    # Extract from OFAC additions
    for ofac in report.get("ofac_additions", []):
        wallet = ofac.get("wallet","").lower()
        if wallet:
            register_wallet(wallet, "ofac", "sanctions_list_addition")
            if wallet in registry:
                registry[wallet]["ofac_match"] = True

    # Prune old entries
    registry = {
        addr: data for addr, data in registry.items()
        if data.get("last_seen","") >= cutoff_date()
    }

    save_json(WALLET_REGISTRY, registry)
    print(f"  Wallet registry: {len(registry)} addresses tracked")
    return registry


# ════════════════════════════════════════════════════════════
# MARKET HISTORY
# ════════════════════════════════════════════════════════════

def update_market_history(report):
    """
    Track markets that matched review criteria across days.
    A market flagged 3+ days in a row is far more significant than a one-time flag.
    """
    history = load_json(MARKET_HISTORY, {})

    for market in report.get("suspicious_market_data", []):
        question  = market.get("question","")
        market_id = market.get("market_id", question[:40])

        if market_id not in history:
            history[market_id] = {
                "question":        question,
                "first_flagged":   TODAY,
                "last_flagged":    TODAY,
                "flag_count":      0,
                "flag_dates":      [],
                "insider_risk":    market.get("insider_risk","MEDIUM"),
                "volume_history":  [],
                "max_wash_score":  0,
                "url":             market.get("url",""),
            }

        h = history[market_id]
        h["last_flagged"]  = TODAY
        h["flag_count"]   += 1
        if TODAY not in h["flag_dates"]:
            h["flag_dates"].append(TODAY)
        h["volume_history"].append({
            "date":   TODAY,
            "volume": market.get("volume_usd",0),
            "prob":   market.get("probability_pct",0),
        })
        h["volume_history"] = h["volume_history"][-30:]

    # Update wash scores from wash trading reports
    for wt in report.get("wash_trading_reports", []):
        qkey = wt.get("question","")[:40]
        for market_id, h in history.items():
            if qkey in h["question"] or h["question"] in qkey:
                h["max_wash_score"] = max(
                    h.get("max_wash_score",0),
                    wt.get("wash_score",0)
                )

    # Prune old markets not seen in 90 days
    history = {
        k: v for k, v in history.items()
        if v.get("last_flagged","") >= cutoff_date()
    }

    save_json(MARKET_HISTORY, history)
    print(f"  Market history: {len(history)} markets tracked")
    return history


# ════════════════════════════════════════════════════════════
# AGGREGATE INTELLIGENCE SUMMARY
# ════════════════════════════════════════════════════════════

def build_aggregate_intelligence(registry, market_history, all_reports):
    """
    Generate the aggregate intelligence summary that powers the dashboard.
    This is what makes patterns visible across days and weeks.
    """

    # Top recurring wallets — seen 2+ times
    recurring_wallets = [
        {
            "address":        addr,
            "short":          addr[:8] + "..." + addr[-6:] if len(addr) > 14 else addr,
            "count":          data["appearance_count"],
            "first_seen":     data["first_seen"],
            "last_seen":      data["last_seen"],
            "signals":        data["signals"][:3],
            "sources":        data["sources"],
            "markets":        data["markets"][:3],
            "max_risk_score": data["max_risk_score"],
            "ofac_match":     data.get("ofac_match", False),
            "watchlist_hit":  data.get("watchlist_hit", False),
            "total_amount":   round(data.get("total_flagged_amount",0), 0),
            "polygonscan":    f"https://polygonscan.com/address/{addr}",
        }
        for addr, data in registry.items()
        if data["appearance_count"] >= 2
    ]
    recurring_wallets = sorted(
        recurring_wallets,
        key=lambda x: (x["ofac_match"], x["watchlist_hit"], x["max_risk_score"], x["count"]),
        reverse=True
    )[:20]

    # High-risk wallets — OFAC or watchlist matches
    high_risk_wallets = [w for w in recurring_wallets if w["ofac_match"] or w["watchlist_hit"]]

    # Persistently flagged markets — seen 2+ days
    persistent_markets = [
        {
            "question":       data["question"],
            "flag_count":     data["flag_count"],
            "first_flagged":  data["first_flagged"],
            "last_flagged":   data["last_flagged"],
            "insider_risk":   data["insider_risk"],
            "max_wash_score": data.get("max_wash_score",0),
            "url":            data.get("url",""),
            "latest_volume":  data["volume_history"][-1]["volume"] if data.get("volume_history") else 0,
            "latest_prob":    data["volume_history"][-1]["prob"] if data.get("volume_history") else 0,
        }
        for data in market_history.values()
        if data["flag_count"] >= 2
    ]
    persistent_markets = sorted(
        persistent_markets,
        key=lambda x: (x["max_wash_score"], x["flag_count"]),
        reverse=True
    )[:10]

    # Daily alert volume trend (last 30 days)
    daily_trend = []
    for i in range(29, -1, -1):
        date = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        report_path = OUTPUT / f"report_{date}.json"
        if report_path.exists():
            try:
                r = json.loads(report_path.read_text())
                daily_trend.append({
                    "date":             date,
                    "news":             r.get("unique_news", len(r.get("alerts",[]))),
                    "suspicious_markets": r.get("suspicious_markets", 0),
                    "large_trades":     r.get("large_trades", 0),
                    "uma_alerts":       r.get("uma_alerts", 0),
                    "ofac_new":         r.get("ofac_new", 0),
                })
            except:
                pass

    # Source frequency analysis
    source_counts = defaultdict(int)
    for report in all_reports:
        for alert in report.get("alerts", []):
            source_counts[alert.get("source","")] += 1

    top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:8]

    # Top keywords across all reports
    keyword_counts = defaultdict(int)
    for report in all_reports:
        for alert in report.get("alerts", []):
            for kw in alert.get("matched_keywords", []):
                keyword_counts[kw] += 1

    top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Win rate tracker summary
    win_data = load_json(DATA / "win_rate_tracker.json", {})
    win_alerts = []
    for wallet, stats in win_data.items():
        resolved = [t for t in stats.get("trades",[]) if t.get("won") is not None]
        if len(resolved) >= 3:
            wins = sum(1 for t in resolved if t["won"])
            rate = wins / len(resolved) * 100
            if rate >= 70:
                win_alerts.append({
                    "wallet":    wallet,
                    "win_rate":  round(rate,1),
                    "trades":    len(resolved),
                    "polygonscan": f"https://polygonscan.com/address/{wallet}",
                })

    aggregate = {
        "generated":          TODAY,
        "days_of_data":       len(daily_trend),
        "total_wallets_tracked": len(registry),
        "total_markets_tracked": len(market_history),
        "recurring_wallets":  recurring_wallets,
        "high_risk_wallets":  high_risk_wallets,
        "persistent_markets": persistent_markets,
        "daily_trend":        daily_trend,
        "top_sources":        [{"source": s, "count": c} for s, c in top_sources],
        "top_keywords":       [{"keyword": k, "count": c} for k, c in top_keywords],
        "win_rate_alerts":    win_alerts,
        "summary_stats": {
            "total_alerts_30d":       sum(d["news"] for d in daily_trend),
            "total_suspicious_30d":   sum(d["suspicious_markets"] for d in daily_trend),
            "wallets_with_ofac":      sum(1 for w in recurring_wallets if w["ofac_match"]),
            "wallets_on_watchlist":   sum(1 for w in recurring_wallets if w["watchlist_hit"]),
            "markets_flagged_3plus":  sum(1 for m in persistent_markets if m["flag_count"] >= 3),
        }
    }

    save_json(AGGREGATE_INTEL, aggregate)
    print(f"  Aggregate intelligence saved — {len(recurring_wallets)} recurring wallets, {len(persistent_markets)} persistent markets")
    return aggregate


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def run_aggregator():
    print(f"Intelligence Aggregator — {TODAY}")

    # Load today's report
    today_report_path = OUTPUT / f"report_{TODAY}.json"
    if not today_report_path.exists():
        print("  No report for today yet — run monitor first")
        return

    today_report = load_json(today_report_path, {})

    # Load all reports for trend analysis
    all_reports = []
    for p in sorted(OUTPUT.glob("report_*.json"), reverse=True)[:30]:
        try:
            all_reports.append(load_json(p, {}))
        except:
            pass

    print(f"  Loaded {len(all_reports)} reports for analysis")

    # Update persistent tracking
    registry        = update_wallet_registry(today_report)
    market_history  = update_market_history(today_report)
    aggregate       = build_aggregate_intelligence(registry, market_history, all_reports)

    print(f"  Done — {aggregate['summary_stats']}")
    return aggregate


from polymarket_monitor.storage.json_store import load_json, save_json


if __name__ == "__main__":
    run_aggregator()
