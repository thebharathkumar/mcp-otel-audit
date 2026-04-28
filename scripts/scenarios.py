"""Run a fixed sequence of MCP scenarios against an instrumented server.

Six scenarios in order. Each scenario opens a fresh ClientSession so that any
session-scoped instrumentation is exercised. Exit code is 0 if all six ran
through (errors *expected* by a scenario don't fail the run); non-zero if
the harness itself broke.

Run:
    uv run --no-project --with 'mcp>=1.0' python scripts/scenarios.py \\
        --target traceloop --endpoint http://localhost:18001/mcp/

Writes a small meta.json next to captures/ with versions and scenario results.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import mcp
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _pkg_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


async def _open(url: str):
    return streamablehttp_client(url)


async def scenario_tool_call_success(url: str) -> dict[str, Any]:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            r = await s.call_tool("echo", {"text": "hello"})
            ok = r.content and getattr(r.content[0], "text", None) == "hello"
            return {"ok": bool(ok), "isError": getattr(r, "isError", False)}


async def scenario_tool_call_with_error(url: str) -> dict[str, Any]:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            r = await s.call_tool("calculate", {"op": "div", "a": 1.0, "b": 0.0})
            return {"isError": bool(getattr(r, "isError", False)),
                    "text": getattr(r.content[0], "text", "") if r.content else ""}


async def scenario_tool_call_with_invalid_args(url: str) -> dict[str, Any]:
    """Send a malformed call_tool payload (wrong type for a required arg).

    Servers may either return isError=True or raise an MCP protocol error.
    Both are valid; we capture whichever path the server uses, because the
    instrumentation should record the failure either way.
    """
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            try:
                r = await s.call_tool("echo", {"text": {"not": "a string"}})
                return {"path": "isError", "isError": bool(getattr(r, "isError", False))}
            except Exception as e:
                return {"path": "exception", "type": type(e).__name__, "msg": str(e)[:200]}


async def scenario_session_lifecycle(url: str) -> dict[str, Any]:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as s:
            init = await s.initialize()
            tools = await s.list_tools()
            return {
                "server": getattr(init.serverInfo, "name", None),
                "protocol": getattr(init, "protocolVersion", None),
                "tool_count": len(tools.tools),
                "tool_names": sorted(t.name for t in tools.tools),
            }


async def scenario_multiple_concurrent_calls(url: str) -> dict[str, Any]:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            inputs = [f"msg-{i}" for i in range(5)]
            results = await asyncio.gather(
                *(s.call_tool("echo", {"text": x}) for x in inputs),
                return_exceptions=True,
            )
            ok = sum(
                1
                for r, x in zip(results, inputs)
                if not isinstance(r, BaseException)
                and r.content
                and getattr(r.content[0], "text", None) == x
            )
            return {"requested": len(inputs), "ok": ok}


async def scenario_streaming_response(url: str) -> dict[str, Any]:
    """The audit's three tools return scalar values; no progress notifications,
    no streamed chunks. We capture this as an explicit "not exercised by these
    tools" data point rather than skipping the scenario, because the absence
    of streaming-related telemetry is itself information about the
    instrumentation surface.
    """
    return {"status": "not_exercised", "reason": "audit tools return scalar values; streaming progress not used"}


SCENARIOS = [
    ("tool_call_success", scenario_tool_call_success),
    ("tool_call_with_error", scenario_tool_call_with_error),
    ("tool_call_with_invalid_args", scenario_tool_call_with_invalid_args),
    ("session_lifecycle", scenario_session_lifecycle),
    ("multiple_concurrent_calls", scenario_multiple_concurrent_calls),
    ("streaming_response", scenario_streaming_response),
]


async def run_all(url: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name, fn in SCENARIOS:
        t0 = time.monotonic()
        try:
            data = await fn(url)
            outcome = {"name": name, "elapsed_s": round(time.monotonic() - t0, 3),
                       "harness_ok": True, "data": data}
        except Exception as e:
            outcome = {"name": name, "elapsed_s": round(time.monotonic() - t0, 3),
                       "harness_ok": False, "error": f"{type(e).__name__}: {e}"}
        results.append(outcome)
        print(f"  [{name}] {'ok' if outcome['harness_ok'] else 'FAIL'} ({outcome['elapsed_s']}s)")
        if not outcome["harness_ok"]:
            print(f"      -> {outcome['error']}")
    return results


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True, help="target name, e.g. traceloop")
    p.add_argument("--endpoint", required=True,
                   help="MCP streamable-http URL, e.g. http://localhost:18001/mcp/")
    p.add_argument("--meta-out", default=None,
                   help="optional path to write a meta.json with versions and results")
    args = p.parse_args()

    print(f"target={args.target} endpoint={args.endpoint}")
    print(f"  mcp_sdk={_pkg_version('mcp')} python={platform.python_version()}")

    started = time.time()
    results = asyncio.run(run_all(args.endpoint))
    elapsed = time.time() - started

    meta = {
        "target": args.target,
        "endpoint": args.endpoint,
        "started_unix": int(started),
        "elapsed_s": round(elapsed, 3),
        "host": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "client_versions": {
            "mcp": _pkg_version("mcp"),
        },
        "scenarios": results,
    }
    if args.meta_out:
        Path(args.meta_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.meta_out).write_text(json.dumps(meta, indent=2) + "\n")
        print(f"meta written: {args.meta_out}")

    n_harness_ok = sum(1 for r in results if r["harness_ok"])
    print(f"harness_ok {n_harness_ok}/{len(results)} in {elapsed:.1f}s")
    return 0 if n_harness_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
