"""OFAC SDN crypto wallet collection and parsing."""

from __future__ import annotations

import json
from typing import Any

import requests

try:
    from defusedxml import ElementTree as SafeET
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as SafeET

from polymarket_monitor import config


def _xml_tag_name(element: Any) -> str:
    return str(element.tag).rsplit("}", 1)[-1]


def _child_text(element: Any, tag_name: str) -> str:
    for child in list(element):
        if _xml_tag_name(child) == tag_name and child.text:
            return child.text.strip()
    return ""


def parse_ofac_crypto_entries(xml_text: str) -> dict[str, dict[str, str]]:
    root = SafeET.fromstring(xml_text)
    current = {}
    for entry in root.iter():
        if _xml_tag_name(entry) != "sdnEntry":
            continue
        uid = _child_text(entry, "uid")
        name = _child_text(entry, "lastName")
        if not uid or not name:
            continue
        for id_tag in entry.iter():
            if _xml_tag_name(id_tag) != "id":
                continue
            id_type = _child_text(id_tag, "idType")
            id_num = _child_text(id_tag, "idNumber")
            if id_type and id_num and "Digital" in id_type:
                current[uid] = {"name": name, "wallet": id_num}
    return current


def fetch_ofac_new() -> list[dict[str, str]]:
    new_entries = []
    try:
        resp = requests.get(
            "https://www.treasury.gov/ofac/downloads/sdn.xml",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        current = parse_ofac_crypto_entries(resp.text)
        seen = set()
        if config.OFAC_SEEN.exists():
            seen = set(json.loads(config.OFAC_SEEN.read_text()))
        for uid, entry in current.items():
            if uid not in seen:
                new_entries.append(entry)
        config.OFAC_SEEN.write_text(json.dumps(list(current.keys()), indent=2))
        config.OFAC_CACHE.write_text(json.dumps(current, indent=2))
    except Exception as e:
        print(f"  OFAC error: {e}")
    if len(new_entries) > 10:
        overflow = len(new_entries) - 10
        new_entries = new_entries[:10]
        new_entries.append({"name": f"+ {overflow} more", "wallet": "See data/ofac_cache.json"})
    print(f"  New OFAC additions: {len(new_entries)}")
    return new_entries

