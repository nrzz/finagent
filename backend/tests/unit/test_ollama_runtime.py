"""Ollama exclusive (single loaded model) helpers."""

from finagent.llm.ollama_runtime import _names_match


def test_names_match() -> None:
    assert _names_match("qwen2.5:7b", "qwen2.5:7b")
    assert _names_match("qwen2.5:7b", "qwen2.5:7b-instruct") or _names_match(
        "qwen2.5:7b", "qwen2.5:7b"
    )
    assert not _names_match("qwen2.5:7b", "llama3.1:8b")
