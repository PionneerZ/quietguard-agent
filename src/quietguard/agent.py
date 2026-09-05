"""Strands agent composition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strands import Agent, tool

from .policy_model import SafetyPolicyModel
from .runtime import QuietGuardRuntime


SYSTEM_PROMPT = """You are QuietGuard, a safety-first disk-pressure agent.
Use the available tools in this order: inspect, plan, optionally apply, publish.
Never invent filesystem evidence. Never act outside explicit marker-based allowlists.
Stay quiet when there is no meaningful pressure or decision."""


def build_tools(runtime: QuietGuardRuntime) -> list[Any]:
    @tool
    def scan_workspace() -> str:
        """Inspect the configured root without following symlinks or reparse points."""
        return json.dumps(runtime.scan(), ensure_ascii=False)

    @tool
    def build_guarded_plan() -> str:
        """Classify evidence and create a byte-capped allowlist-only action plan."""
        return json.dumps(runtime.build_plan(), ensure_ascii=False)

    @tool
    def apply_safe_actions() -> str:
        """Apply only the precomputed actions that pass every filesystem guard."""
        return json.dumps(runtime.apply_plan(), ensure_ascii=False)

    @tool
    def publish_dashboard() -> str:
        """Write the incident JSON, visual dashboard, and final audit evidence."""
        return json.dumps(runtime.report(), ensure_ascii=False)

    return [scan_workspace, build_guarded_plan, apply_safe_actions, publish_dashboard]


def run_cycle(
    root: Path,
    output_dir: Path,
    *,
    apply_mode: bool = False,
    min_age_hours: float = 1.0,
    max_auto_bytes: int = 512 * 1024 * 1024,
    attention_bytes: int = 1024 * 1024,
) -> dict[str, Any]:
    runtime = QuietGuardRuntime(
        root,
        output_dir,
        apply_mode=apply_mode,
        min_age_hours=min_age_hours,
        max_auto_bytes=max_auto_bytes,
        attention_bytes=attention_bytes,
    )
    model = SafetyPolicyModel(apply_mode=apply_mode)
    agent = Agent(
        name="QuietGuard",
        model=model,
        tools=build_tools(runtime),
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )
    prompt = (
        f"Run one autonomous disk-pressure cycle for {runtime.root}. "
        f"Mode is {'apply allowlisted actions' if apply_mode else 'read-only'}. "
        "Publish evidence when finished."
    )
    runtime.audit("strands_agent_started", {"model": model.get_config(), "tool_count": 4})
    result = agent(prompt)
    runtime.audit("strands_agent_finished", {"result": str(result)})
    return {
        "result": str(result),
        "summary": runtime.summary,
        "plan": runtime.plan,
        "execution": runtime.execution,
        "dashboard": str(runtime.output_dir / "dashboard.html"),
        "report": str(runtime.output_dir / "incident-report.json"),
        "audit": str(runtime.output_dir / "audit.jsonl"),
    }