"""indexergo.com — Korean macro / market data series.

The site renders ECharts; the relevant `series.data` array sits inline as JSON
inside one of the `<script>` blocks. We balance-bracket scan that array to be
robust against nested objects (markPoint, etc.) the chart engine includes.
"""
from __future__ import annotations

import re
from typing import Any

from ..http import http_get


# ---- low-level page parser ----

def _url(detail_id: str, frq: str) -> str:
    if frq.upper() == "Q":
        return f"https://www.indexergo.com/series/?detailId={detail_id}&frq={frq}"
    return f"https://www.indexergo.com/series/?frq={frq}&idxDetail={detail_id}"


def _extract_series_pairs(html: str) -> list[tuple[str, float]]:
    for s in re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", html):
        if '"series"' not in s or "echarts.init" not in s:
            continue
        sidx = s.find('"series"')
        didx = s.find('"data"', sidx)
        if didx < 0:
            continue
        b = s.find("[", didx)
        if b < 0:
            continue
        depth = 0
        in_str = False
        esc = False
        end = -1
        for j in range(b, len(s)):
            ch = s[j]
            if esc:
                esc = False
                continue
            if in_str:
                if ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        if end < 0:
            continue
        arr = s[b:end]
        return [
            (label, float(v))
            for label, v in re.findall(
                r'\[\s*"([^"]+)"\s*,\s*(-?[0-9.]+)\s*\]', arr
            )
        ]
    return []


def fetch_series(detail_id: str, frq: str) -> list[tuple[str, float]]:
    """Return raw [(label, value), ...] pairs as rendered on the page."""
    html = http_get(_url(detail_id, frq)).decode("utf-8", errors="replace")
    return _extract_series_pairs(html)


# ---- date helpers ----

def norm_daily(label: str) -> str | None:
    m = re.match(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})$", label.strip())
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


def norm_quarter(label: str) -> str | None:
    m = re.match(r"^(\d{4})\.([1-4])/4$", label.strip())
    return f"{m.group(1)}Q{m.group(2)}" if m else None


def quarter_for_date(date_iso: str) -> str:
    y, mo, _ = date_iso.split("-")
    return f"{y}Q{(int(mo) - 1) // 3 + 1}"


# ---- known series presets ----

KOSPI_FEAR_GREED = ("24501", "D")
KOSPI_MARKET_CAP = ("20104", "D")
KOREA_GDP_QUARTERLY = ("09140", "Q")


def fetch_kospi_fear_greed() -> dict[str, Any]:
    pairs = fetch_series(*KOSPI_FEAR_GREED)
    series = [{"date": norm_daily(d) or d, "value": v} for d, v in pairs]
    return {
        "name": "코스피 공포탐욕지수",
        "source": _url(*KOSPI_FEAR_GREED),
        "latest": series[-1] if series else None,
        "series": series,
    }


def _compute_buffett(market_cap_pairs, gdp_pairs):
    quarterly = []
    for label, v in gdp_pairs:
        q = norm_quarter(label)
        if q:
            quarterly.append((q, v))
    quarterly.sort()

    annual_at: dict[str, float] = {}
    for i in range(3, len(quarterly)):
        annual_at[quarterly[i][0]] = sum(v for _, v in quarterly[i - 3 : i + 1])
    sorted_q = sorted(annual_at)

    def annual_for(date_iso: str) -> float | None:
        target = quarter_for_date(date_iso)
        candidate = None
        for sq in sorted_q:
            if sq <= target:
                candidate = sq
            else:
                break
        return annual_at.get(candidate) if candidate else None

    out = []
    for label, mc in market_cap_pairs:
        d = norm_daily(label)
        if not d:
            continue
        ag = annual_for(d)
        if not ag:
            continue
        out.append({
            "date": d,
            "market_cap_trn_krw": mc,
            "annual_gdp_trn_krw": round(ag, 4),
            "buffett_pct": round(mc / ag * 100, 2),
        })
    return out


def fetch_kospi_buffett() -> dict[str, Any]:
    mc = fetch_series(*KOSPI_MARKET_CAP)
    gdp = fetch_series(*KOREA_GDP_QUARTERLY)
    series = _compute_buffett(mc, gdp)
    return {
        "name": "코스피 버핏지수",
        "formula": "시가총액 / 직전 4Q GDP 합 × 100",
        "sources": {
            "market_cap": _url(*KOSPI_MARKET_CAP),
            "gdp": _url(*KOREA_GDP_QUARTERLY),
        },
        "latest": series[-1] if series else None,
        "series": series,
        "raw_market_cap": [
            {"date": norm_daily(d) or d, "value": v} for d, v in mc
        ],
        "raw_gdp": [
            {"period": norm_quarter(d) or d, "value": v} for d, v in gdp
        ],
    }
