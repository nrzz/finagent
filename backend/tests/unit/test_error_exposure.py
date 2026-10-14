"""Provider failures must not leak exception text into chat responses (py/stack-trace-exposure)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from finagent.agent.loop import PROVIDER_FAILED_MESSAGE, AgentLoop
from finagent.config.schema import ToolMode

SECRET_DETAIL = "401 Unauthorized for https://llm.internal.example/v1 (key=sk-live-123)"


class _FailingRouter:
    """Stands in for the LLM router; every completion fails with a detailed message."""

    def __init__(self, mode: ToolMode) -> None:
        self.mode = mode

    def effective_tool_mode(self) -> ToolMode:
        return self.mode

    async def complete(self, messages: list[dict[str, Any]], **_: Any) -> dict[str, Any]:
        raise RuntimeError(SECRET_DETAIL)


@pytest.fixture(params=[ToolMode.JSON_FALLBACK, ToolMode.NATIVE], ids=["json", "native"])
def failing_router(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> ToolMode:
    mode: ToolMode = request.param
    monkeypatch.setattr("finagent.agent.loop.get_llm_router", lambda: _FailingRouter(mode))
    return mode


@pytest.mark.asyncio
async def test_run_returns_a_generic_message_and_audits_the_cause(failing_router: ToolMode) -> None:
    audited: list[tuple[str, dict[str, Any]]] = []

    async def audit(action: str, detail: dict[str, Any]) -> None:
        audited.append((action, detail))

    result = await AgentLoop(audit=audit).run("hello")
    assert result["content"] == PROVIDER_FAILED_MESSAGE
    assert "sk-live-123" not in json.dumps(result)
    assert [action for action, _ in audited] == ["agent_error"]


@pytest.mark.asyncio
async def test_stream_events_emit_a_generic_error_then_done(failing_router: ToolMode) -> None:
    events = [event async for event in AgentLoop().stream_events("hello")]
    assert events[-2:] == [
        {"type": "error", "message": PROVIDER_FAILED_MESSAGE},
        {"type": "done"},
    ]
    assert "sk-live-123" not in json.dumps(events)
    assert "llm.internal.example" not in json.dumps(events)
