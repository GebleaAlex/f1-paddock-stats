"""Command line: `paddock fetch`, `paddock build`, `paddock update` (both), `paddock serve`."""

from __future__ import annotations

import argparse
import time


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="paddock", description="Paddock Stats data pipeline and API")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="download f1db and Jolpica into data/raw")
    fetch.add_argument("--f1db-tag", help="f1db release tag (default: latest)")
    sub.add_parser("build", help="build data/paddock.duckdb from data/raw")
    update = sub.add_parser("update", help="fetch, then build")
    update.add_argument("--f1db-tag")
    timing = sub.add_parser("timing", help="download 2018+ timing, tyres and telemetry through FastF1, then rebuild")
    timing.add_argument("--years", type=int, nargs="+", required=True)
    timing.add_argument("--sessions", nargs="+", default=["Q", "SQ", "S", "R"], help="Q SQ S R")
    timing.add_argument("--limit", type=int, help="stop after this many sessions")
    timing.add_argument("--no-build", action="store_true", help="do not rebuild the database afterwards")
    timing.add_argument(
        "--wait",
        action="store_true",
        help="when FastF1's hourly request limit is reached, wait and continue until done",
    )
    sub.add_parser("mcp", help="run the MCP server on stdio (for Claude Desktop, Claude Code and other MCP clients)")
    serve = sub.add_parser("serve", help="run the API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8020)
    serve.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    if args.command in ("fetch", "update"):
        from .sources import fetch_all

        started = time.perf_counter()
        for s in fetch_all(f1db_tag=args.f1db_tag):
            print(f"{s['name']:<12} {s['version']:<14} {s['licence']}")
        print(f"fetched in {time.perf_counter() - started:.1f}s")
    if args.command in ("build", "update"):
        from .build import build

        started = time.perf_counter()
        path = build()
        print(f"built {path} in {time.perf_counter() - started:.1f}s")
    if args.command == "timing":
        from .timing import run

        started = time.perf_counter()
        result = run(args.years, set(args.sessions), args.limit)
        while args.wait and result["stopped"] == "rate limit":
            print("request limit reached; waiting an hour before continuing", flush=True)
            if result["done"] and not args.no_build:
                from .build import build

                print(f"built {build()}", flush=True)
            time.sleep(3700)
            more = run(args.years, set(args.sessions), args.limit)
            more["done"] = result["done"] + more["done"]
            more["failed"] = result["failed"] + more["failed"]
            result = more
        print(
            f"timing: {len(result['done'])} sessions processed, {result['skipped']} already there, "
            f"{len(result['failed'])} failed in {time.perf_counter() - started:.0f}s"
            + (f"; stopped: {result['stopped']}, run again to continue" if result["stopped"] else "")
        )
        for f in result["failed"]:
            print("  failed:", f)
        if result["done"] and not args.no_build:
            from .build import build

            print(f"built {build()}")
    if args.command == "mcp":
        from .mcp_server import main as run_mcp

        run_mcp()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("paddock.api.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
