"""LLM JSON parse helpers."""

import re
import time

import anyio
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finagent.llm.router import LLMRouter, _fenced_json_object, parse_json_tool_payload


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


def test_intent_price_of_aapl_is_quote_not_options() -> None:
    import json

    from finagent.llm.router import intent_tool_json

    payload = json.loads(
        intent_tool_json([{"role": "user", "content": "What is the price of AAPL?"}])["content"]
    )
    assert payload["tool"] == "get_quote"
    assert payload["arguments"]["symbol"] == "AAPL"


def test_intent_option_chain_still_works() -> None:
    import json

    from finagent.llm.router import intent_tool_json

    payload = json.loads(
        intent_tool_json([{"role": "user", "content": "Show NIFTY option chain"}])["content"]
    )
    assert payload["tool"] == "get_option_chain"
    assert payload["arguments"]["symbol"] == "NIFTY"


# --- fenced-block extraction (py/polynomial-redos fix) -------------------------------------

# The pattern parse_json_tool_payload used before the fix. Kept only as the reference the linear
# scanner must agree with; it is quadratic on hostile input, so it only ever sees tiny strings.
_REFERENCE_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('```json\n{"final":"hi"}\n```', '{"final":"hi"}'),
        ('```{"a":1}```', '{"a":1}'),
        ('Sure!\n```json\n{"a": 1}\n```\nbye', '{"a": 1}'),
        ('```json\n{"a": {"b": 1}}\n```', '{"a": {"b": 1}}'),
        ('```python\nprint(1)\n```\n```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```{ "a": "}" } ```', '{ "a": "}" }'),
        ("```json   \n\n  {}  \n  ```", "{}"),
        # a "}" that is not followed by the closing fence does not end the object
        ('```{"a": 1} and {"b": 2}```', '{"a": 1} and {"b": 2}'),
        # the closing fence may sit past other fences (the object is not paired fence by fence)
        ("```{ a ``` b }```", "{ a ``` b }"),
        # no match: no fence, unterminated, wrong tag case, no object, opening fence only
        ('{"a": 1}', None),
        ('```json\n{"a": 1}', None),
        ('```JSON\n{"a": 1}\n```', None),
        ("```\nplain text\n```", None),
        ("```{", None),
        ("```", None),
        ("", None),
    ],
)
def test_fenced_json_object_cases(text: str, expected: str | None) -> None:
    assert _fenced_json_object(text) == expected
    match = _REFERENCE_FENCE.search(text)
    assert (match.group(1) if match else None) == expected


@settings(max_examples=600, deadline=None)
@given(
    st.lists(
        st.sampled_from(["```", "``", "`", "json", "{", "}", " ", "\n", "x", '"']), max_size=24
    ).map("".join)
)
def test_fenced_json_object_matches_reference_regex(text: str) -> None:
    match = _REFERENCE_FENCE.search(text)
    assert _fenced_json_object(text) == (match.group(1) if match else None)


def test_parse_prefers_the_fenced_object_over_other_braces() -> None:
    text = 'Use {curly} braces like so:\n```json\n{"final": "ok"}\n```\nand {more} text'
    assert parse_json_tool_payload(text) == {"final": "ok"}


def test_parse_without_fence_still_uses_outermost_braces() -> None:
    assert parse_json_tool_payload('noise {"tool": "get_quote", "arguments": {}} tail') == {
        "tool": "get_quote",
        "arguments": {},
    }


# Keyed by short names: pytest puts parameter ids in an environment variable (32k limit on Windows)
_HOSTILE_INPUTS = {
    "unclosed-objects": "```{" * 50_000,  # every fence opens an object that is never closed
    "unfenced-braces": "```{" + "} " * 100_000,  # many "}" candidates, none before a fence
    "empty-fences": "``` " * 100_000,  # many fences, none opening an object
    "overlapping-fences": "````" * 50_000,
    "whitespace-run": "```" + " " * 1_000_000,
}


@pytest.mark.parametrize("name", sorted(_HOSTILE_INPUTS))
def test_fence_scan_is_linear_on_hostile_input(name: str) -> None:
    hostile = _HOSTILE_INPUTS[name]
    started = time.perf_counter()
    assert _fenced_json_object(hostile) is None
    assert parse_json_tool_payload(hostile) is None
    # Linear scans finish in milliseconds; the old regex needed minutes on the first input.
    assert time.perf_counter() - started < 2.0
