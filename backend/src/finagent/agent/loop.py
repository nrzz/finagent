"""Agent tool-calling loop with audit trail and iteration caps."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from finagent.agent.tools import TOOLS_SCHEMA, execute_tool
from finagent.config import get_settings
from finagent.config.schema import ToolMode
from finagent.llm import JSON_TOOL_SYSTEM, get_llm_router, parse_json_tool_payload
from finagent.logging_setup import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """You are FinAgent, a self-hosted finance AI agent.
Rules:
1. Use tools for all market numbers. Cite source and as_of/timestamp from tool results.
2. Never invent prices, NAVs, or portfolio values.
3. You cannot enable live trading, change settings, or read API keys.
4. Prefer paper trading. Label all recommendations as not financial advice.
5. Be concise and actionable. Use markdown.
"""

AuditCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class AgentLoop:
    def __init__(self, audit: AuditCallback | None = None) -> None:
        self.audit = audit

    async def _audit(self, action: str, detail: dict[str, Any]) -> None:
        if self.audit:
            await self.audit(action, detail)

    async def run(
        self, user_message: str, history: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        router = get_llm_router()
        mode = router.effective_tool_mode()
        max_iters = get_settings().llm.max_tool_iterations
        citations: list[dict[str, Any]] = []
        tool_trace: list[dict[str, Any]] = []

        if mode == ToolMode.JSON_FALLBACK:
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": JSON_TOOL_SYSTEM},
                *(history or []),
                {"role": "user", "content": user_message},
            ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *(history or []),
                {"role": "user", "content": user_message},
            ]

        for _ in range(max_iters):
            if mode == ToolMode.JSON_FALLBACK:
                result = await router.complete(messages)
                payload = parse_json_tool_payload(result.get("content") or "")
                if not payload:
                    # repair retry
                    messages.append({"role": "assistant", "content": result.get("content") or ""})
                    messages.append(
                        {
                            "role": "user",
                            "content": 'Respond with ONLY JSON: {"tool":"...","arguments":{...}} or {"final":"..."}',
                        }
                    )
                    continue
                if "final" in payload:
                    answer = str(payload["final"])
                    await self._audit("agent_final", {"mode": "json-fallback"})
                    return {"content": answer, "tool_trace": tool_trace, "citations": citations}
                name = str(payload.get("tool", ""))
                args = payload.get("arguments") or {}
                allowed = {
                    "get_quote",
                    "get_option_chain",
                    "get_portfolio",
                    "place_paper_order",
                    "run_screener",
                    "search_symbols",
                }
                if name not in allowed:
                    messages.append({"role": "assistant", "content": json.dumps(payload)})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f'Unknown tool "{name}". Use ONLY one of: '
                                + ", ".join(sorted(allowed))
                                + '. Reply with ONLY JSON: {"tool":"get_quote","arguments":{"symbol":"..."}} '
                                'or {"final":"..."}'
                            ),
                        }
                    )
                    continue
                tool_result = await execute_tool(name, args)
                tool_trace.append(tool_result)
                await self._audit(
                    "tool_call", {"tool": name, "args": args, "ok": tool_result.get("ok")}
                )
                if tool_result.get("ok") and isinstance(tool_result.get("result"), dict):
                    r = tool_result["result"]
                    if "source" in r or "as_of" in r:
                        citations.append(r)
                messages.append({"role": "assistant", "content": json.dumps(payload)})
                messages.append(
                    {
                        "role": "user",
                        "content": "Tool result:\n" + json.dumps(tool_result) + "\nContinue.",
                    }
                )
                continue

            # Native tool calling
            result = await router.complete(messages, tools=TOOLS_SCHEMA)
            tool_calls = result.get("tool_calls") or []
            if not tool_calls:
                content = result.get("content") or ""
                await self._audit("agent_final", {"mode": "native"})
                return {"content": content, "tool_trace": tool_trace, "citations": citations}

            messages.append(
                {
                    "role": "assistant",
                    "content": result.get("content") or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                tool_result = await execute_tool(tc["name"], tc["arguments"])
                tool_trace.append(tool_result)
                await self._audit(
                    "tool_call",
                    {"tool": tc["name"], "args": tc["arguments"], "ok": tool_result.get("ok")},
                )
                if tool_result.get("ok") and isinstance(tool_result.get("result"), dict):
                    r = tool_result["result"]
                    if "source" in r or "as_of" in r:
                        citations.append(r)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": json.dumps(tool_result),
                    }
                )

        return {
            "content": "I hit the tool-iteration limit. Please refine your question.",
            "tool_trace": tool_trace,
            "citations": citations,
        }

    async def stream_events(
        self, user_message: str, history: list[dict[str, Any]] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield SSE-friendly events: tool_start, tool_result, token, final."""
        # For simplicity, run full loop then stream the final answer tokens for UX;
        # emit tool events from the completed trace.
        yield {"type": "status", "message": "Thinking…"}
        result = await self.run(user_message, history)
        for t in result.get("tool_trace") or []:
            yield {"type": "tool_result", "data": t}
        content = result.get("content") or ""
        # chunk tokens for streaming feel
        chunk_size = 24
        for i in range(0, len(content), chunk_size):
            yield {"type": "token", "content": content[i : i + chunk_size]}
        yield {
            "type": "final",
            "content": content,
            "citations": result.get("citations") or [],
            "tool_trace": result.get("tool_trace") or [],
        }
