"""JSON persistence helpers for local monitor state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polymarket_monitor import config


def load_json(path: str | Path, default: Any) -> Any:
    path = Path(path)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return default
    return default


def save_json(path: str | Path, data: Any) -> None:
    Path(path).write_text(json.dumps(data, indent=2))


def load_seen_articles(path: Path = config.SEEN_ARTICLES) -> set[str]:
    return set(load_json(path, []))


def save_seen_articles(urls: set[str], path: Path = config.SEEN_ARTICLES, limit: int = 500) -> None:
    existing = load_seen_articles(path)
    all_urls = list(existing | urls)[-limit:]
    save_json(path, all_urls)


def load_story_threads(path: Path = config.STORY_THREADS) -> dict[str, Any]:
    return load_json(path, {})


def save_story_threads(threads: dict[str, Any], path: Path = config.STORY_THREADS) -> None:
    save_json(path, threads)


def load_win_rate(path: Path = config.WIN_RATE_FILE) -> dict[str, Any]:
    return load_json(path, {})


def save_win_rate(data: dict[str, Any], path: Path = config.WIN_RATE_FILE) -> None:
    save_json(path, data)

