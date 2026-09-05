"""Filesystem inspection, safety planning, guarded action, and reporting."""

from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SAFE_MARKER = ".quietguard-safe"
SAFE_SUFFIXES = {".log", ".tmp", ".trace", ".dmp"}
PROTECTED_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".pdf", ".jpg", ".jpeg", ".png", ".mp4", ".zip",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@dataclass(frozen=True)
class Finding:
    path: str
    size_bytes: int
    age_hours: float
    growth_bytes: int
    classification: str
    reason: str


class QuietGuardRuntime:
    """Stateful runtime shared by Strands tools for one incident cycle."""

    def __init__(
        self,
        root: Path,
        output_dir: Path,
        *,
        apply_mode: bool = False,
        min_age_hours: float = 1.0,
        max_auto_bytes: int = 512 * 1024 * 1024,
        attention_bytes: int = 1024 * 1024,
    ) -> None:
        self.root = root.expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError(f"Root is not a directory: {self.root}")
        self.output_dir = output_dir.expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.apply_mode = apply_mode
        self.min_age_hours = min_age_hours
        self.max_auto_bytes = max_auto_bytes
        self.attention_bytes = attention_bytes
        self.findings: list[Finding] = []
        self.plan: dict[str, Any] = {}
        self.execution: dict[str, Any] = {"status": "not_requested", "reclaimed_bytes": 0, "actions": []}
        self.summary: dict[str, Any] = {}
        self._audit_path = self.output_dir / "audit.jsonl"
        self._audit_seq = 0
        self._audit_hash = "GENESIS"
        self.audit("cycle_started", {"root": str(self.root), "apply_mode": apply_mode})

    def audit(self, event: str, data: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "seq": self._audit_seq + 1,
            "timestamp": utc_now(),
            "event": event,
            "data": data,
            "previous_hash": self._audit_hash,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        record = {**payload, "hash": digest}
        with self._audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._audit_seq += 1
        self._audit_hash = digest
        return record

    @staticmethod
    def _is_reparse(path: Path) -> bool:
        try:
            attrs = path.lstat().st_file_attributes
        except (AttributeError, OSError):
            attrs = 0
        flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return path.is_symlink() or bool(attrs & flag)

    def _within_root(self, path: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(self.root)
            return True
        except ValueError:
            return False

    def _has_safe_marker(self, path: Path) -> bool:
        current = path.parent
        while self._within_root(current):
            if self._is_reparse(current):
                return False
            if (current / SAFE_MARKER).is_file():
                return True
            if current == self.root:
                break
            current = current.parent
        return False

    def _load_baseline(self) -> dict[str, Any]:
        path = self.output_dir / "baseline.json"
        if not path.exists():
            return {"timestamp": None, "files": {}}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"timestamp": None, "files": {}}
        except (OSError, json.JSONDecodeError):
            return {"timestamp": None, "files": {}}

    def scan(self) -> dict[str, Any]:
        baseline = self._load_baseline()
        baseline_files = baseline.get("files", {}) if isinstance(baseline.get("files", {}), dict) else {}
        now = datetime.now(timezone.utc).timestamp()
        findings: list[Finding] = []
        skipped_reparse: list[str] = []
        stack = [self.root]

        while stack:
            directory = stack.pop()
            try:
                entries = list(os.scandir(directory))
            except (OSError, PermissionError) as exc:
                self.audit("scan_error", {"path": str(directory), "error": type(exc).__name__})
                continue
            for entry in entries:
                path = Path(entry.path)
                try:
                    if entry.is_symlink() or self._is_reparse(path):
                        skipped_reparse.append(str(path))
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(path)
                        continue
                    if not entry.is_file(follow_symlinks=False) or path.name == SAFE_MARKER:
                        continue
                    details = entry.stat(follow_symlinks=False)
                except OSError:
                    continue

                relative = path.relative_to(self.root).as_posix()
                previous = baseline_files.get(relative, {})
                prior_size = int(previous.get("size_bytes", details.st_size)) if isinstance(previous, dict) else details.st_size
                growth = max(0, details.st_size - prior_size)
                age_hours = max(0.0, (now - details.st_mtime) / 3600)
                suffix = path.suffix.lower()
                marked = self._has_safe_marker(path)
                if marked and suffix in SAFE_SUFFIXES:
                    classification = "auto_safe" if age_hours >= self.min_age_hours else "observe"
                    reason = "allowlist marker + safe extension" if classification == "auto_safe" else "too recent for automation"
                elif suffix in PROTECTED_SUFFIXES:
                    classification = "protected"
                    reason = "user data or stateful file type"
                elif suffix in SAFE_SUFFIXES:
                    classification = "review_required"
                    reason = "log-like file lacks an explicit allowlist marker"
                else:
                    classification = "protected"
                    reason = "unknown file type defaults to protected"
                findings.append(
                    Finding(relative, details.st_size, round(age_hours, 3), growth, classification, reason)
                )

        findings.sort(key=lambda item: item.size_bytes, reverse=True)
        self.findings = findings
        disk = shutil.disk_usage(self.root)
        safe_bytes = sum(item.size_bytes for item in findings if item.classification == "auto_safe")
        growth_bytes = sum(item.growth_bytes for item in findings)
        if safe_bytes >= self.attention_bytes or growth_bytes >= self.attention_bytes:
            status = "attention"
        else:
            status = "quiet"
        self.summary = {
            "status": status,
            "root": str(self.root),
            "scanned_files": len(findings),
            "safe_candidate_bytes": safe_bytes,
            "growth_bytes": growth_bytes,
            "free_bytes": disk.free,
            "skipped_reparse_points": skipped_reparse,
        }
        new_baseline = {
            "timestamp": utc_now(),
            "files": {item.path: {"size_bytes": item.size_bytes} for item in findings},
        }
        (self.output_dir / "baseline.json").write_text(
            json.dumps(new_baseline, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.audit("scan_completed", self.summary)
        return {**self.summary, "findings": [asdict(item) for item in findings]}

    def build_plan(self) -> dict[str, Any]:
        if not self.findings:
            raise RuntimeError("scan_workspace must run before build_guarded_plan")
        candidates = [item for item in self.findings if item.classification == "auto_safe"]
        selected: list[dict[str, Any]] = []
        planned = 0
        for item in sorted(candidates, key=lambda entry: (-entry.age_hours, -entry.size_bytes)):
            if planned + item.size_bytes > self.max_auto_bytes:
                continue
            selected.append({"path": item.path, "size_bytes": item.size_bytes, "action": "delete"})
            planned += item.size_bytes
        escalations = [
            asdict(item) for item in self.findings if item.classification == "review_required"
        ]
        self.plan = {
            "status": "actionable" if selected else "observe",
            "selected": selected,
            "planned_reclaim_bytes": planned,
            "budget_bytes": self.max_auto_bytes,
            "escalations": escalations,
            "guardrails": [
                "exact resolved root boundary",
                f"ancestor {SAFE_MARKER} marker",
                "safe extension allowlist",
                f"minimum age {self.min_age_hours:g} hours",
                "symlink and reparse-point refusal",
                "cycle byte budget",
            ],
        }
        self.audit("plan_built", self.plan)
        return self.plan

    def apply_plan(self) -> dict[str, Any]:
        if not self.apply_mode:
            raise RuntimeError("apply mode is disabled")
        if not self.plan:
            raise RuntimeError("build_guarded_plan must run before apply_safe_actions")
        actions: list[dict[str, Any]] = []
        reclaimed = 0
        for item in self.plan.get("selected", []):
            relative = Path(str(item["path"]))
            candidate = self.root / relative
            result = {"path": relative.as_posix(), "expected_bytes": int(item["size_bytes"])}
            if not self._within_root(candidate):
                result.update(status="refused", reason="outside_root")
            elif self._is_reparse(candidate) or not self._has_safe_marker(candidate):
                result.update(status="refused", reason="marker_or_reparse_guard")
            elif candidate.suffix.lower() not in SAFE_SUFFIXES:
                result.update(status="refused", reason="extension_guard")
            elif not candidate.is_file():
                result.update(status="skipped", reason="missing")
            else:
                actual = candidate.stat().st_size
                candidate.unlink()
                reclaimed += actual
                result.update(status="deleted", reclaimed_bytes=actual)
            actions.append(result)
            self.audit("action_checked", result)
        self.execution = {"status": "completed", "reclaimed_bytes": reclaimed, "actions": actions}
        self.audit("execution_completed", self.execution)
        return self.execution

    def report(self) -> dict[str, Any]:
        report = {
            "generated_at": utc_now(),
            "agent": "QuietGuard",
            "framework": "Strands Agents SDK",
            "model_policy": "quietguard-offline-safety-policy-v1",
            "summary": self.summary,
            "plan": self.plan,
            "execution": self.execution,
            "findings": [asdict(item) for item in self.findings],
            "audit": {"path": str(self._audit_path), "last_hash": self._audit_hash, "events": self._audit_seq},
        }
        json_path = self.output_dir / "incident-report.json"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        dashboard_path = self.output_dir / "dashboard.html"
        dashboard_path.write_text(self._dashboard(report), encoding="utf-8")
        self.audit("report_published", {"json": str(json_path), "dashboard": str(dashboard_path)})
        return {"json": str(json_path), "dashboard": str(dashboard_path), "status": self.summary.get("status")}

    def _dashboard(self, report: dict[str, Any]) -> str:
        summary = report["summary"]
        plan = report["plan"]
        execution = report["execution"]
        findings = report["findings"]
        rows = "".join(
            "<tr><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td><td><span class='pill {}'>{}</span></td></tr>".format(
                html.escape(item["path"]),
                format_bytes(item["size_bytes"]),
                format_bytes(item["growth_bytes"]),
                f"{item['age_hours']:.1f}h",
                html.escape(item["classification"]),
                html.escape(item["classification"].replace("_", " ")),
            )
            for item in findings
        )
        payload = html.escape(json.dumps(report, ensure_ascii=False))
        return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>QuietGuard incident dashboard</title>
<style>
:root{{--ink:#101b2d;--muted:#60708a;--paper:#f4f7fb;--card:#fff;--cyan:#19c3b1;--amber:#ffb547;--red:#e85d75;--navy:#13233f}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(145deg,#eef6ff,#f8fbff 45%,#effbf8);color:var(--ink);font:15px/1.5 Inter,Segoe UI,sans-serif}}
main{{max-width:1180px;margin:auto;padding:36px 24px 64px}} header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:26px}}
h1{{font-size:42px;letter-spacing:-1.5px;margin:0}} h2{{font-size:20px;margin:0 0 14px}} .eyebrow{{color:#0b7f75;font-weight:800;text-transform:uppercase;letter-spacing:1.8px}}
.sub{{color:var(--muted);max-width:680px}} .status{{padding:10px 16px;border-radius:999px;background:#fff3d8;color:#815100;font-weight:800;border:1px solid #ffd98d}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}} .card{{background:rgba(255,255,255,.92);border:1px solid #dfe7f1;border-radius:18px;padding:20px;box-shadow:0 12px 32px #2033540c}}
.metric{{font-size:29px;font-weight:850;letter-spacing:-.8px}} .label{{color:var(--muted);font-size:13px}} .wide{{grid-column:span 3}} .side{{grid-column:span 1}}
.bar{{height:13px;background:#edf1f6;border-radius:10px;overflow:hidden;margin:13px 0}} .bar i{{display:block;height:100%;width:min(100%,{(plan.get('planned_reclaim_bytes',0)/max(1,summary.get('safe_candidate_bytes',1))*100):.1f}%);background:linear-gradient(90deg,var(--cyan),#56d88b)}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;padding:12px;border-bottom:1px solid #edf1f6}} th{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.7px}}
code{{color:#29415f}} .pill{{padding:4px 9px;border-radius:999px;font-size:12px;font-weight:800}} .auto_safe{{background:#d9f8ef;color:#087066}} .protected{{background:#e9eef6;color:#53627a}} .review_required{{background:#fff0d4;color:#875300}} .observe{{background:#e8e3ff;color:#6049a8}}
.gate{{background:var(--navy);color:white}} .gate p{{color:#cbd7ea}} .checks{{display:grid;gap:9px}} .checks div:before{{content:'✓';color:#4ce0c3;margin-right:9px;font-weight:900}} footer{{color:var(--muted);margin-top:18px;font-size:12px}}
@media(max-width:850px){{.grid{{grid-template-columns:1fr 1fr}}.wide,.side{{grid-column:span 2}}header{{align-items:flex-start;flex-direction:column}}}} @media(max-width:520px){{.grid{{grid-template-columns:1fr}}.wide,.side{{grid-column:span 1}}}}
</style></head><body><main>
<header><div><div class='eyebrow'>QuietGuard / autonomous incident</div><h1>Disk pressure, handled quietly.</h1><p class='sub'>A Strands agent scanned the workspace, built a bounded plan, and surfaced only the files that need a human decision.</p></div><div class='status'>{html.escape(summary.get('status','unknown').upper())}</div></header>
<section class='grid'>
<article class='card'><div class='label'>Files inspected</div><div class='metric'>{summary.get('scanned_files',0)}</div></article>
<article class='card'><div class='label'>Safe candidates</div><div class='metric'>{format_bytes(summary.get('safe_candidate_bytes',0))}</div></article>
<article class='card'><div class='label'>Growth detected</div><div class='metric'>{format_bytes(summary.get('growth_bytes',0))}</div></article>
<article class='card'><div class='label'>Actually reclaimed</div><div class='metric'>{format_bytes(execution.get('reclaimed_bytes',0))}</div></article>
<article class='card wide'><h2>Guarded action plan</h2><div class='bar'><i></i></div><p><b>{len(plan.get('selected',[]))}</b> allowlisted actions, capped at <b>{format_bytes(plan.get('budget_bytes',0))}</b>. <b>{len(plan.get('escalations',[]))}</b> items need review.</p></article>
<article class='card side gate'><h2>Decision gate</h2><p>{'Automation completed inside the allowlist.' if execution.get('status') == 'completed' else 'Read-only mode. No file was changed.'}</p><div class='checks'><div>Root bound</div><div>Marker required</div><div>Reparse refused</div><div>Budget capped</div></div></article>
</section>
<article class='card'><h2>Evidence table</h2><div style='overflow:auto'><table><thead><tr><th>Path</th><th>Size</th><th>Growth</th><th>Age</th><th>Decision</th></tr></thead><tbody>{rows}</tbody></table></div></article>
<footer>Tamper-evident audit chain: {html.escape(self._audit_hash[:20])}… · No external scripts or network calls. <span data-report='{payload}'></span></footer>
</main></body></html>"""


