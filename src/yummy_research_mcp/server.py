"""MCP stdio server exposing 해외·국내 통계/시장 지표."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from . import __version__
from .sources import cnn, indexergo

log = logging.getLogger("yummy-research-mcp")
server: Server = Server("yummy-research")


# ---------- tool registry ----------
# Adding a new tool: drop another entry here. Each fetcher is sync; we run it
# in a worker thread so the MCP event loop stays responsive.

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


def _t_cnn_fng(args: dict[str, Any]) -> dict[str, Any]:
    return cnn.fetch_fear_greed(max_history=args.get("max_history"))


def _t_kospi_fng(_: dict[str, Any]) -> dict[str, Any]:
    return indexergo.fetch_kospi_fear_greed()


def _t_kospi_buffett(_: dict[str, Any]) -> dict[str, Any]:
    return indexergo.fetch_kospi_buffett()


def _t_all(_: dict[str, Any]) -> dict[str, Any]:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cnn_fear_and_greed": cnn.fetch_fear_greed(),
        "kospi_fear_and_greed": indexergo.fetch_kospi_fear_greed(),
        "kospi_buffett": indexergo.fetch_kospi_buffett(),
    }


TOOLS: dict[str, tuple[Tool, ToolFn]] = {
    "get_cnn_fear_greed": (
        Tool(
            name="get_cnn_fear_greed",
            description=(
                "CNN Fear & Greed Index — 미국 시장 심리 (0=공포, 100=탐욕). "
                "현재값(이전 종가/1주/1개월/1년 비교 포함) + 일별 히스토리(약 254 영업일)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_history": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "히스토리 시계열을 최근 N개로 자르기. 생략 시 전체.",
                    }
                },
                "additionalProperties": False,
            },
        ),
        _t_cnn_fng,
    ),
    "get_kospi_fear_greed": (
        Tool(
            name="get_kospi_fear_greed",
            description="코스피 공포탐욕지수 (인덱서고 idxDetail=24501, 일간) — 현재값 + 영업일 시계열.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        _t_kospi_fng,
    ),
    "get_kospi_buffett": (
        Tool(
            name="get_kospi_buffett",
            description=(
                "코스피 버핏지수 = 코스피 시가총액 / 직전 4Q GDP 합 × 100 (%). "
                "원시 시총·GDP 시계열 동봉."
            ),
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        _t_kospi_buffett,
    ),
    "get_all_indices": (
        Tool(
            name="get_all_indices",
            description="등록된 모든 지표를 한 번에 fetched_at 타임스탬프와 함께 반환.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        _t_all,
    ),
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [tool for tool, _ in TOOLS.values()]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    entry = TOOLS.get(name)
    if entry is None:
        return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]
    _, fn = entry
    args = arguments or {}
    try:
        payload = await asyncio.to_thread(fn, args)
    except Exception as e:  # noqa: BLE001 — surface any fetcher error to the model
        log.exception("tool %s failed", name)
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False),
        )]
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


async def _amain() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("yummy-research-mcp v%s starting (stdio)", __version__)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
