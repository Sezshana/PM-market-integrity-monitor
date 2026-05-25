"""Polygonscan/Etherscan wallet context helpers."""

from __future__ import annotations

import datetime
from typing import Any

import requests

from polymarket_monitor import config

USDC_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"


def get_wallet_age(address: str) -> str | None:
    if not config.POLYGONSCAN_KEY:
        return None
    try:
        resp = requests.get("https://api.polygonscan.com/api", params={
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "sort": "asc",
            "apikey": config.POLYGONSCAN_KEY,
            "offset": 1,
            "page": 1,
        }, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            ts = int(data["result"][0].get("timeStamp", 0))
            if ts:
                return datetime.datetime.fromtimestamp(ts).date().isoformat()
    except Exception:
        pass
    return None


def get_wallet_tx_count(address: str) -> int:
    if not config.POLYGONSCAN_KEY:
        return 999
    try:
        resp = requests.get("https://api.polygonscan.com/api", params={
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "sort": "desc",
            "apikey": config.POLYGONSCAN_KEY,
            "offset": 100,
            "page": 1,
        }, timeout=10)
        data = resp.json()
        if data.get("status") == "1":
            return len(data.get("result", []))
    except Exception:
        pass
    return 999


def get_funding_wallet(address: str) -> str | None:
    try:
        resp = requests.get("https://api.polygonscan.com/api", params={
            "module": "account",
            "action": "tokentx",
            "address": address,
            "contractaddress": USDC_POLYGON,
            "sort": "asc",
            "apikey": config.POLYGONSCAN_KEY,
            "offset": 5,
            "page": 1,
        }, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            return data["result"][0].get("from", "")
    except Exception:
        pass
    return None

