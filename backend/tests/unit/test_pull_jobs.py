"""Unit tests for Ollama pull progress helpers."""

from finagent.llm.pull_jobs import PullProgress, _map_phase


def test_map_phase() -> None:
    assert _map_phase("pulling manifest") == "manifest"
    assert _map_phase("downloading") == "downloading"
    assert _map_phase("verifying sha256 digest") == "verifying"
    assert _map_phase("success") == "success"


def test_progress_to_dict() -> None:
    p = PullProgress(
        model="qwen2.5:7b", phase="downloading", percent=42.5, total_bytes=100, completed_bytes=42
    )
    d = p.to_dict()
    assert d["model"] == "qwen2.5:7b"
    assert d["percent"] == 42.5
    assert d["running"] is True
