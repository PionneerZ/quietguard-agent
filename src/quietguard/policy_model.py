"""An offline policy model that drives the real Strands agent loop.

The deterministic provider makes the safety demo reproducible and free to run.
Production deployments can swap it for any Strands-supported model provider;
the tools and guardrails stay unchanged.
"""

from __future__ import annotations

import json
import threading
from collections.abc import AsyncIterable
from typing import Any

from strands.models import Model
from strands.types.content import Messages, SystemContentBlock
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec


class SafetyPolicyModel(Model):
    """Choose the next safety tool from a fixed, reviewable policy."""

    def __init__(self, *, apply_mode: bool = False) -> None:
        self.config: dict[str, Any] = {
            "model_id": "quietguard-offline-safety-policy-v1",
            "apply_mode": apply_mode,
            "context_window_limit": 16_000,
        }
        self._counter = 0

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return dict(self.config)

    async def structured_output(self, output_model: type[Any], prompt: Messages, system_prompt: str | None = None, **kwargs: Any):
        if False:  # pragma: no cover - keeps this an async generator for the SDK interface.
            yield {}
        raise NotImplementedError("QuietGuard uses tool events rather than structured model output")

    @staticmethod
    def _used_tools(messages: Messages) -> set[str]:
        names: set[str] = set()
        for message in messages:
            for block in message.get("content", []):
                tool_use = block.get("toolUse")
                if tool_use and tool_use.get("name"):
                    names.add(str(tool_use["name"]))
        return names

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        system_prompt_content: list[SystemContentBlock] | None = None,
        invocation_state: dict[str, Any] | None = None,
        cancel_signal: threading.Event | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        used = self._used_tools(messages)
        order = ["scan_workspace", "build_guarded_plan"]
        if self.config.get("apply_mode"):
            order.append("apply_safe_actions")
        order.append("publish_dashboard")

        next_tool = next((name for name in order if name not in used), None)
        yield {"messageStart": {"role": "assistant"}}
        if next_tool:
            self._counter += 1
            tool_id = f"quietguard_{self._counter:02d}"
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"name": next_tool, "toolUseId": tool_id}}
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps({})}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            message = (
                "QuietGuard completed the scan, guarded plan, "
                + ("allowlisted cleanup, " if self.config.get("apply_mode") else "read-only review, ")
                + "and tamper-evident dashboard publication."
            )
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": message}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "metrics": {"latencyMs": 0},
            }
        }


