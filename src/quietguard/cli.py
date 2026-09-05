"""Command-line interface for QuietGuard."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from .agent import run_cycle
from .demo import create_demo_workspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QuietGuard autonomous disk-pressure agent")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="scan a directory and publish an incident dashboard")
    run.add_argument("root", type=Path)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--apply", action="store_true", help="apply only marker-based allowlisted actions")
    run.add_argument("--min-age-hours", type=float, default=1.0)
    run.add_argument("--max-auto-mb", type=float, default=512.0)
    run.add_argument("--attention-mb", type=float, default=1.0)

    demo = sub.add_parser("demo", help="create and resolve a contained synthetic log storm")
    demo.add_argument("--output", type=Path, default=None)
    demo.add_argument("--read-only", action="store_true")

    serve = sub.add_parser("serve", help="serve an evidence directory locally")
    serve.add_argument("directory", type=Path)
    serve.add_argument("--port", type=int, default=8768)
    return parser


def _run(args: argparse.Namespace) -> dict:
    return run_cycle(
        args.root,
        args.output,
        apply_mode=args.apply,
        min_age_hours=args.min_age_hours,
        max_auto_bytes=int(args.max_auto_mb * 1024 * 1024),
        attention_bytes=int(args.attention_mb * 1024 * 1024),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "run":
        result = _run(args)
    elif args.command == "demo":
        base = args.output or Path("artifacts") / f"demo-{datetime.now():%Y%m%d-%H%M%S}"
        workspace, evidence = create_demo_workspace(base)
        result = run_cycle(
            workspace,
            evidence,
            apply_mode=not args.read_only,
            min_age_hours=1.0,
            max_auto_bytes=8 * 1024 * 1024,
            attention_bytes=512 * 1024,
        )
        result["demo_workspace"] = str(workspace)
    else:
        directory = args.directory.resolve(strict=True)
        os.chdir(directory)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(SimpleHTTPRequestHandler, directory=str(directory)))
        print(f"QuietGuard dashboard: http://127.0.0.1:{args.port}/dashboard.html")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


