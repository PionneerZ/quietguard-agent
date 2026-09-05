from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from quietguard.agent import run_cycle
from quietguard.runtime import QuietGuardRuntime


def write(path: Path, size: int = 64) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def marked_fixture(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "root"
    safe = root / "logs"
    safe.mkdir(parents=True)
    (safe / ".quietguard-safe").write_text("test", encoding="utf-8")
    write(safe / "old.log", 128)
    old = time.time() - 7200
    os.utime(safe / "old.log", (old, old))
    write(root / "business.db", 96)
    write(root / "unmarked" / "unknown.log", 80)
    return root, tmp_path / "evidence"


def test_scan_classifies_explicit_allowlist_and_protects_data(tmp_path: Path) -> None:
    root, evidence = marked_fixture(tmp_path)
    runtime = QuietGuardRuntime(root, evidence, attention_bytes=1)
    result = runtime.scan()
    by_path = {item["path"]: item for item in result["findings"]}
    assert by_path["logs/old.log"]["classification"] == "auto_safe"
    assert by_path["business.db"]["classification"] == "protected"
    assert by_path["unmarked/unknown.log"]["classification"] == "review_required"


def test_apply_removes_only_marker_allowlisted_files(tmp_path: Path) -> None:
    root, evidence = marked_fixture(tmp_path)
    result = run_cycle(root, evidence, apply_mode=True, attention_bytes=1)
    assert not (root / "logs" / "old.log").exists()
    assert (root / "business.db").exists()
    assert (root / "unmarked" / "unknown.log").exists()
    assert result["execution"]["reclaimed_bytes"] == 128
    assert Path(result["dashboard"]).exists()


def test_outside_root_plan_is_refused(tmp_path: Path) -> None:
    root, evidence = marked_fixture(tmp_path)
    outside = tmp_path / "outside.log"
    write(outside, 72)
    runtime = QuietGuardRuntime(root, evidence, apply_mode=True, attention_bytes=1)
    runtime.scan()
    runtime.build_plan()
    runtime.plan["selected"].append({"path": "../outside.log", "size_bytes": 72, "action": "delete"})
    result = runtime.apply_plan()
    assert outside.exists()
    assert any(item.get("reason") == "outside_root" for item in result["actions"])


def test_byte_budget_skips_oversized_candidate(tmp_path: Path) -> None:
    root, evidence = marked_fixture(tmp_path)
    runtime = QuietGuardRuntime(root, evidence, apply_mode=True, max_auto_bytes=100, attention_bytes=1)
    runtime.scan()
    plan = runtime.build_plan()
    assert plan["selected"] == []
    assert (root / "logs" / "old.log").exists()


def test_reparse_or_symlink_is_never_scanned(tmp_path: Path) -> None:
    root, evidence = marked_fixture(tmp_path)
    outside = tmp_path / "outside"
    write(outside / "escape.log", 32)
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")
    runtime = QuietGuardRuntime(root, evidence, attention_bytes=1)
    result = runtime.scan()
    assert str(link) in result["skipped_reparse_points"]
    assert all("escape.log" not in item["path"] for item in result["findings"])


def test_audit_chain_is_verifiable(tmp_path: Path) -> None:
    root, evidence = marked_fixture(tmp_path)
    result = run_cycle(root, evidence, apply_mode=False, attention_bytes=1)
    previous = "GENESIS"
    records = [json.loads(line) for line in Path(result["audit"]).read_text(encoding="utf-8").splitlines()]
    assert len(records) >= 6
    for record in records:
        digest = record.pop("hash")
        assert record["previous_hash"] == previous
        expected = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        assert digest == expected
        previous = digest


def test_real_strands_agent_invokes_expected_tool_order(tmp_path: Path) -> None:
    root, evidence = marked_fixture(tmp_path)
    result = run_cycle(root, evidence, apply_mode=False, attention_bytes=1)
    records = [json.loads(line) for line in Path(result["audit"]).read_text(encoding="utf-8").splitlines()]
    events = [record["event"] for record in records]
    assert "strands_agent_started" in events
    assert events.index("scan_completed") < events.index("plan_built") < events.index("report_published")
    assert "QuietGuard completed" in result["result"]


