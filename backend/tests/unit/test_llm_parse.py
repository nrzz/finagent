"""LLM JSON parse helpers."""

from finagent.llm.router import parse_json_tool_payload


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
