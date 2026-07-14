"""LLM JSON parse helpers."""

import anyio

from finagent.llm.router import LLMRouter, parse_json_tool_payload


def test_parse_final() -> None:
    p = parse_json_tool_payload('{"final":"hello"}')
    assert p is not None
    assert p["final"] == "hello"


def test_parse_fenced_tool() -> None:
    text = """Here you go
```json
{"tool":"get_quote","arguments":{"symbol":"AAPL"}}
```
"""
    p = parse_json_tool_payload(text)
    assert p is not None
    assert p["tool"] == "get_quote"


def test_parse_invalid() -> None:
    assert parse_json_tool_payload("not json") is None


def test_demo_paper_buy_skips_paper_word() -> None:
    async def _run() -> dict:
        router = LLMRouter()
        # Force demo complete path
        from finagent.config import get_settings
        from finagent.config.schema import LLMProvider

        get_settings().llm.provider = LLMProvider.DEMO
        return await router._complete_once([{"role": "user", "content": "Paper-buy 10 AAPL"}])

    result = anyio.run(_run)
    import json

    payload = json.loads(result["content"])
    assert payload["tool"] == "place_paper_order"
    assert payload["arguments"]["symbol"] == "AAPL"
    assert payload["arguments"]["quantity"] == "10"
