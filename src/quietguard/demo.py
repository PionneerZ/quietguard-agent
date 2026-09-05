"""Create a repeatable incident fixture without touching user files."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def _write_sized(path: Path, size: int, byte: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        chunk = byte * min(size, 64 * 1024)
        remaining = size
        while remaining:
            part = chunk[: min(len(chunk), remaining)]
            handle.write(part)
            remaining -= len(part)


def create_demo_workspace(base: Path) -> tuple[Path, Path]:
    base = base.resolve()
    workspace = base / "workspace"
    evidence = base / "evidence"
    if workspace.exists() or evidence.exists():
        raise FileExistsError(f"Demo output already exists: {base}")
    safe = workspace / "Diagnostics" / "EXCEL"
    safe.mkdir(parents=True)
    (safe / ".quietguard-safe").write_text(
        "Explicit demo-only allowlist. QuietGuard may remove old .log/.tmp/.trace/.dmp files below this directory.\n",
        encoding="utf-8",
    )
    _write_sized(safe / "Primary001.log", 2 * 1024 * 1024)
    _write_sized(safe / "session.tmp", 1024 * 1024)
    _write_sized(workspace / "Business" / "customer.sqlite", 640 * 1024, b"d")
    _write_sized(workspace / "Unmarked" / "mystery.log", 768 * 1024, b"?")
    old = time.time() - 8 * 3600
    os.utime(safe / "Primary001.log", (old, old))
    os.utime(safe / "session.tmp", (old, old))
    evidence.mkdir(parents=True)
    baseline = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files": {
            "Diagnostics/EXCEL/Primary001.log": {"size_bytes": 256 * 1024},
            "Diagnostics/EXCEL/session.tmp": {"size_bytes": 128 * 1024},
            "Business/customer.sqlite": {"size_bytes": 640 * 1024},
            "Unmarked/mystery.log": {"size_bytes": 512 * 1024},
        },
    }
    (evidence / "baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    return workspace, evidence