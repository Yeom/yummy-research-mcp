"""Smoke tests — hit live endpoints. Skip if offline.

    uv run pytest
"""
from __future__ import annotations

import pytest
import os
pytestmark=pytest.mark.skipif(os.environ.get("YUMMY_LIVE_TESTS")!="1",reason="Live network test; set YUMMY_LIVE_TESTS=1")

from yummy_research_mcp.sources import cnn, indexergo


def test_cnn_fear_greed():
    out = cnn.fetch_fear_greed(max_history=5)
    score = out["latest"]["score"]
    assert score is not None and 0 <= float(score) <= 100
    assert len(out["series"]) <= 5
    assert out["series"][-1]["date"]


def test_kospi_fear_greed():
    out = indexergo.fetch_kospi_fear_greed()
    assert out["series"], "no data points"
    last = out["latest"]
    assert last and 0 <= last["value"] <= 100


def test_kospi_buffett():
    out = indexergo.fetch_kospi_buffett()
    assert out["series"]
    last = out["latest"]
    assert last and last["buffett_pct"] > 0
    assert last["market_cap_trn_krw"] > 0
    assert last["annual_gdp_trn_krw"] > 0


if __name__ == "__main__":
    pytest.main([__file__])
