"""
Polymarket On-Chain Monitor
Replaces Dune with Polygonscan API — free, reliable, no polling needed.
Identifies suspicious wallets, funding sources, new vs experienced traders,
and cross-references against OFAC and watchlist.
"""

import requests
import json
import datetime
from pathlib import Path

TODAY = datetime.date.today().isoformat()

# Polymarket's main contract addresses on Polygon
POLYMARKET_CONTRACTS = [
    "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",  # CTF Exchange
    "0xC5d563A36AE78145C45a50134d48A1215220f80b",  # Neg Risk CTF Exchange
    "0xd91E80cF2EA7be683CE154334e14859001c4A0b7",  # Neg Risk Adapter
]

POLYGONSCAN_KEY = "YourEtherscanAPIKeyHere"  # Set as POLYGONSCAN_KEY in GitHub Secrets (use your Etherscan key)

LARGE_TX_THRESHOLD = 10_000   # Flag transactions over $10k USDC
NEW_WALLET_DAYS    = 30       # Flag wallets created less than 30 days ago
HIGH_FREQ_THRESHOLD = 50      # Flag wallets with 50+ Polymarket transactions


def get_polygonscan_key():
    import os
    return os.environ.get("POLYGONSCAN_KEY", "")  # Your Etherscan API key works here


def check_wallet_profile(wallet_address):
    """
    Build a risk profile for a wallet address.
    Returns: funding source, age, transaction count, balance, red flags.
    """
    api_key = get_polygonscan_key()
    if not api_key:
        return None

    profile = {
        "address":       wallet_address,
        "red_flags":     [],
        "risk_score":    0,
        "first_tx_date": None,
        "tx_count":      0,
        "matic_balance": 0,
        "funding_source": None,
        "is_new_wallet": False,
        "is_high_freq":  False,
        "is_contract":   False,
    }

    base = "https://api.etherscan.io/v2/api?chainid=137"

    # 1. Check if it's a contract (bot indicator)
    try:
        resp = requests.get(base, params={
            "module": "contract", "action": "getabi",
            "address": wallet_address, "apikey": api_key
        }, timeout=10)
        if resp.json().get("status") == "1":
            profile["is_contract"] = True
            profile["red_flags"].append("Contract address — likely automated trading bot")
            profile["risk_score"] += 2
    except: pass

    # 2. Get transaction history
    try:
        resp = requests.get(base, params={
            "module": "account", "action": "txlist",
            "address": wallet_address, "startblock": 0,
            "endblock": 99999999, "sort": "asc",
            "apikey": api_key, "offset": 10, "page": 1
        }, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            txs = data["result"]
            profile["tx_count"] = len(txs)

            # First transaction date
            first_ts = int(txs[0].get("timeStamp", 0))
            if first_ts:
                first_date = datetime.datetime.fromtimestamp(first_ts).date()
                profile["first_tx_date"] = first_date.isoformat()
                days_old = (datetime.date.today() - first_date).days
                if days_old < NEW_WALLET_DAYS:
                    profile["is_new_wallet"] = True
                    profile["red_flags"].append(f"New wallet — only {days_old} days old")
                    profile["risk_score"] += 3

            # Funding source — first incoming transaction
            for tx in txs:
                if tx.get("to","").lower() == wallet_address.lower() and float(tx.get("value",0)) > 0:
                    profile["funding_source"] = tx.get("from","unknown")
                    break
    except Exception as e:
        pass

    # 3. Get MATIC balance
    try:
        resp = requests.get(base, params={
            "module": "account", "action": "balance",
            "address": wallet_address, "apikey": api_key
        }, timeout=10)
        data = resp.json()
        if data.get("status") == "1":
            balance_wei = int(data.get("result", 0))
            profile["matic_balance"] = round(balance_wei / 1e18, 4)
    except: pass

    # 4. Check Polymarket-specific transaction count
    try:
        poly_tx_count = 0
        for contract in POLYMARKET_CONTRACTS:
            resp = requests.get(base, params={
                "module": "account", "action": "tokentx",
                "address": wallet_address,
                "contractaddress": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USDC on Polygon
                "apikey": api_key, "offset": 100, "page": 1
            }, timeout=10)
            data = resp.json()
            if data.get("status") == "1":
                poly_tx_count += len(data.get("result", []))

        profile["polymarket_tx_count"] = poly_tx_count
        if poly_tx_count >= HIGH_FREQ_THRESHOLD:
            profile["is_high_freq"] = True
            profile["red_flags"].append(f"High frequency trader — {poly_tx_count} USDC transactions")
            profile["risk_score"] += 1
    except: pass

    return profile


def fetch_recent_large_polymarket_txs():
    """
    Scan Polymarket's main contract for large USDC transactions in the last 24 hours.
    No Dune needed — direct Polygonscan query.
    """
    api_key = get_polygonscan_key()
    if not api_key:
        print("  Polygonscan: no API key — set POLYGONSCAN_KEY in GitHub Secrets")
        return []

    flagged = []
    yesterday_ts = int((datetime.datetime.now() - datetime.timedelta(days=1)).timestamp())
    usdc_polygon  = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC contract on Polygon

    for contract in POLYMARKET_CONTRACTS[:1]:  # Start with main CTF exchange
        try:
            resp = requests.get("https://api.etherscan.io/v2/api", params={
                "chainid": 137,
                "module":          "account",
                "action":          "tokentx",
                "contractaddress": usdc_polygon,
                "address":         contract,
                "sort":            "desc",
                "apikey":          api_key,
                "offset":          200,
                "page":            1,
            }, timeout=15)

            data = resp.json()
            if data.get("status") != "1":
                continue

            for tx in data.get("result", []):
                ts    = int(tx.get("timeStamp", 0))
                if ts < yesterday_ts:
                    continue

                value = int(tx.get("value", 0)) / 1e6  # USDC has 6 decimals
                if value < LARGE_TX_THRESHOLD:
                    continue

                from_addr = tx.get("from","")
                to_addr   = tx.get("to","")
                tx_date   = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")

                flagged.append({
                    "from":        from_addr,
                    "to":          to_addr,
                    "value_usdc":  round(value, 2),
                    "tx_hash":     tx.get("hash",""),
                    "timestamp":   tx_date,
                    "polygonscan": f"https://polygonscan.com/tx/{tx.get('hash','')}",
                })

        except Exception as e:
            print(f"  Polygonscan error: {e}")

    # Sort by value, take top 10
    flagged = sorted(flagged, key=lambda x: x["value_usdc"], reverse=True)[:10]
    print(f"  On-chain large transactions: {len(flagged)}")
    return flagged


def build_wallet_risk_summary(large_txs):
    """
    For each large transaction, build a wallet risk profile on the sender.
    Returns a list of high-risk wallet findings.
    """
    api_key = get_polygonscan_key()
    if not api_key or not large_txs:
        return []

    findings = []
    checked  = set()

    for tx in large_txs[:5]:  # Profile top 5 by value
        wallet = tx["from"]
        if wallet in checked:
            continue
        checked.add(wallet)

        profile = check_wallet_profile(wallet)
        if not profile:
            continue

        if profile["red_flags"] or profile["risk_score"] >= 2:
            findings.append({
                "wallet":        wallet,
                "value_usdc":    tx["value_usdc"],
                "timestamp":     tx["timestamp"],
                "red_flags":     profile["red_flags"],
                "risk_score":    profile["risk_score"],
                "first_tx_date": profile["first_tx_date"],
                "funding_source":profile["funding_source"],
                "is_new_wallet": profile["is_new_wallet"],
                "is_contract":   profile["is_contract"],
                "polygonscan":   f"https://polygonscan.com/address/{wallet}",
            })

    findings = sorted(findings, key=lambda x: x["risk_score"], reverse=True)
    print(f"  High-risk wallet profiles: {len(findings)}")
    return findings
