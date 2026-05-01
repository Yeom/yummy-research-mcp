"""CNN Fear & Greed Index — US market sentiment (0=fear, 100=greed)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..http import http_get

API = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
PAGE = "https://edition.cnn.com/markets/fear-and-greed"


def fetch_fear_greed(max_history: int | None = None) -> dict[str, Any]:
    body = http_get(
        API,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://edition.cnn.com",
            "Referer": "https://edition.cnn.com/",
        },
    )
    raw = json.loads(body)
    cur = raw.get("fear_and_greed", {}) or {}
    hist = (raw.get("fear_and_greed_historical") or {}).get("data", []) or []

    series: list[dict[str, Any]] = []
    for p in hist:
        if isinstance(p, dict):
            ts_ms = p.get("x") or p.get("timestamp")
            score = p.get("y") or p.get("score")
            rating = p.get("rating")
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            ts_ms, score = p[0], p[1]
            rating = p[2] if len(p) > 2 else None
        else:
            continue
        if ts_ms is None or score is None:
            continue
        date = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
        series.append({"date": date, "score": round(float(score), 4), "rating": rating})

    if max_history and len(series) > max_history:
        series = series[-max_history:]

    return {
        "name": "CNN Fear & Greed Index",
        "source": PAGE,
        "latest": {
            "score": cur.get("score"),
            "rating": cur.get("rating"),
            "timestamp": cur.get("timestamp"),
            "previous_close": cur.get("previous_close"),
            "previous_1_week": cur.get("previous_1_week"),
            "previous_1_month": cur.get("previous_1_month"),
            "previous_1_year": cur.get("previous_1_year"),
        },
        "series": series,
    }
