"""SSRF guard for LLM / Ollama endpoints (code-scanning alert py/full-ssrf).

Every outbound LLM request must start from ``validate_llm_base_url`` plus a fixed path.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import httpx
import pytest

from finagent.config import get_env
from finagent.config.schema import LLMConfig, LLMProvider
from finagent.llm import pull_jobs
from finagent.llm.ollama_runtime import ensure_exclusive_model, ollama_base_url
from finagent.llm.router import LLMRouter, _endpoint
from finagent.security.url_safety import (
    LLM_ALLOWED_HOSTS_ENV,
    assert_llm_base_url,
    is_safe_llm_base_url,
    validate_llm_base_url,
)


@pytest.fixture(autouse=True)
def _no_operator_allow_list(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Start every test from the default policy, whatever the developer's environment says."""
    monkeypatch.delenv(LLM_ALLOWED_HOSTS_ENV, raising=False)
    get_env.cache_clear()
    yield
    get_env.cache_clear()


def _patch_httpx(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


# --- validate_llm_base_url ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "canonical"),
    [
        ("http://localhost:11434", "http://localhost:11434"),
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434"),
        ("http://127.0.0.1:1234/v1", "http://127.0.0.1:1234/v1"),
        ("http://127.8.9.10:11434", "http://127.8.9.10:11434"),  # all of 127/8 is loopback
        ("http://[::1]:11434", "http://[::1]:11434"),
        ("HTTP://LocalHost:11434/", "http://localhost:11434"),
        ("http://localhost.:11434", "http://localhost:11434"),
        ("  http://localhost:11434/v1/  ", "http://localhost:11434/v1"),
        ("https://api.openai.com/v1", "https://api.openai.com/v1"),
        ("https://api.anthropic.com", "https://api.anthropic.com"),
        ("https://api.anthropic.com/", "https://api.anthropic.com"),
        ("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1"),
        ("https://api.groq.com/openai/v1", "https://api.groq.com/openai/v1"),
        ("https://eu.api.openai.com/v1", "https://eu.api.openai.com/v1"),
        (
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "https://generativelanguage.googleapis.com/v1beta/openai",
        ),
    ],
)
def test_default_policy_accepts_local_and_known_cloud_endpoints(url: str, canonical: str) -> None:
    assert validate_llm_base_url(url) == canonical


def test_ipv4_mapped_loopback_is_loopback() -> None:
    assert validate_llm_base_url("http://[::ffff:127.0.0.1]:11434").startswith("http://[")


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        # not a usable URL
        ("", "empty"),
        ("   ", "empty"),
        ("localhost:11434", "http:// or https://"),
        ("//localhost:11434", "http:// or https://"),
        ("javascript:alert(1)", "http:// or https://"),
        ("ftp://localhost:11434", "http:// or https://"),
        ("file:///etc/passwd", "http:// or https://"),
        ("gopher://localhost:70", "http:// or https://"),
        ("http://", "no host"),
        ("http:///v1", "no host"),
        ("http://local host:11434", "spaces or control"),
        ("http://localhost:11434/v1\nHost: evil.example", "spaces or control"),
        ("http://localhost:11434/" + "a" * 3000, "too long"),
        # credentials, query, fragment
        ("http://user:pw@localhost:11434", "username or password"),
        ("http://localhost:11434@evil.example", "username or password"),
        ("https://api.openai.com@evil.example/v1", "username or password"),
        ("http://localhost\\@evil.example", "username or password"),
        ("http://localhost:11434/?x=1", "query string or fragment"),
        ("http://localhost:11434/v1#frag", "query string or fragment"),
        ("http://localhost:11434?", "query string or fragment"),
        # ports
        ("http://localhost:99999", "port"),
        ("http://localhost:abc", "port"),
        ("http://localhost:0", "port"),
        # path tricks
        ("http://localhost:11434/../admin", "path"),
        ("http://localhost:11434/./x", "path"),
        ("http://localhost:11434//x", "path"),
        ("http://localhost:11434/%2e%2e/x", "path"),
        ("http://localhost:11434/a;b", "path"),
        # malformed host names
        ("http://exa$mple.com", "invalid host name"),
        ("http://-bad.example", "invalid host name"),
        ("http://a..b", "invalid host name"),
        # never allowed: metadata, link-local, unspecified, multicast
        ("http://169.254.169.254/latest/meta-data", "blocked"),
        ("http://[::ffff:169.254.169.254]/", "blocked"),
        ("http://[fe80::1]:11434", "blocked"),
        ("http://0.0.0.0:11434", "blocked"),
        ("http://[::]:11434", "blocked"),
        ("http://224.0.0.1:11434", "blocked"),
        ("http://metadata.google.internal/computeMetadata/v1", "metadata"),
        # LAN, Docker, public hosts need the operator allow-list
        ("http://192.168.1.50:11434", LLM_ALLOWED_HOSTS_ENV),
        ("http://10.0.0.5:11434", LLM_ALLOWED_HOSTS_ENV),
        ("http://172.16.0.9:11434", LLM_ALLOWED_HOSTS_ENV),
        ("http://gpu-box.lan:11434", LLM_ALLOWED_HOSTS_ENV),
        ("http://ollama:11434", LLM_ALLOWED_HOSTS_ENV),
        ("http://[fd00:ec2::254]/", LLM_ALLOWED_HOSTS_ENV),
        ("http://8.8.8.8/", LLM_ALLOWED_HOSTS_ENV),
        ("https://evil.example.com/v1", LLM_ALLOWED_HOSTS_ENV),
        # numeric spellings of loopback are not IP literals, so they stay unlisted names
        ("http://2130706433:11434", LLM_ALLOWED_HOSTS_ENV),
        ("http://0x7f.0.0.1:11434", LLM_ALLOWED_HOSTS_ENV),
        ("http://127.1:11434", LLM_ALLOWED_HOSTS_ENV),
        ("http://0177.0.0.1:11434", LLM_ALLOWED_HOSTS_ENV),
        # look-alikes of the known cloud hosts
        ("https://api.openai.com.evil.example/v1", LLM_ALLOWED_HOSTS_ENV),
        ("https://evilopenrouter.ai/api/v1", LLM_ALLOWED_HOSTS_ENV),
        ("https://notapi.openai.com.evil.example", LLM_ALLOWED_HOSTS_ENV),
        ("http://api.openai.com/v1", "HTTPS"),
        ("http://openrouter.ai/api/v1", "HTTPS"),
    ],
)
def test_default_policy_refuses(url: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        validate_llm_base_url(url)


def test_operator_allow_list_extends_the_default_policy() -> None:
    allowed = ["192.168.1.50", "gpu-box.lan", "ollama", "[fd00::5]"]
    assert (
        validate_llm_base_url("http://192.168.1.50:11434", allowed_hosts=allowed)
        == "http://192.168.1.50:11434"
    )
    assert (
        validate_llm_base_url("https://GPU-BOX.lan/v1/", allowed_hosts=allowed)
        == "https://gpu-box.lan/v1"
    )
    assert validate_llm_base_url("http://ollama:11434", allowed_hosts=allowed) == (
        "http://ollama:11434"
    )
    assert validate_llm_base_url("http://[fd00::5]:8000/v1", allowed_hosts=allowed) == (
        "http://[fd00::5]:8000/v1"
    )
    # only the listed hosts, nothing next to them
    for url in ("http://192.168.1.51:11434", "http://other-box.lan", "https://evil.example.com"):
        with pytest.raises(ValueError, match=LLM_ALLOWED_HOSTS_ENV):
            validate_llm_base_url(url, allowed_hosts=allowed)


@pytest.mark.parametrize(
    ("entry", "url"),
    [
        ("169.254.169.254", "http://169.254.169.254/latest/meta-data"),
        ("fe80::1", "http://[fe80::1]/"),
        ("0.0.0.0", "http://0.0.0.0:11434"),
        ("224.0.0.1", "http://224.0.0.1/"),
        ("metadata.google.internal", "http://metadata.google.internal/computeMetadata/v1"),
    ],
)
def test_allow_list_never_unlocks_metadata_or_link_local_hosts(entry: str, url: str) -> None:
    with pytest.raises(ValueError, match="blocked"):
        validate_llm_base_url(url, allowed_hosts=[entry])


def test_allow_list_entries_are_forgiving_about_ports_urls_and_junk() -> None:
    allowed = [
        "192.168.1.50:11434",
        "http://gpu-box.lan:8000/v1",
        " , ",
        "bad host!",
        "UPPER.example",
    ]
    assert validate_llm_base_url("http://192.168.1.50:1", allowed_hosts=allowed)
    assert validate_llm_base_url("http://gpu-box.lan", allowed_hosts=allowed)
    assert validate_llm_base_url("https://upper.example/v1", allowed_hosts=allowed)
    with pytest.raises(ValueError):
        validate_llm_base_url("http://bad", allowed_hosts=allowed)


def test_operator_allow_list_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match=LLM_ALLOWED_HOSTS_ENV):
        validate_llm_base_url("http://192.168.1.50:11434")
    monkeypatch.setenv(LLM_ALLOWED_HOSTS_ENV, "192.168.1.50, gpu-box.lan")
    get_env.cache_clear()
    assert validate_llm_base_url("http://192.168.1.50:11434") == "http://192.168.1.50:11434"
    assert validate_llm_base_url("https://gpu-box.lan/v1") == "https://gpu-box.lan/v1"
    with pytest.raises(ValueError):
        validate_llm_base_url("http://192.168.1.99:11434")


def test_legacy_helpers_follow_the_same_policy() -> None:
    assert is_safe_llm_base_url(None) == (True, "ok")
    assert is_safe_llm_base_url("") == (True, "ok")
    assert is_safe_llm_base_url("http://127.0.0.1:11434") == (True, "ok")
    ok, reason = is_safe_llm_base_url("http://169.254.169.254/")
    assert ok is False
    assert "blocked" in reason
    assert_llm_base_url(None)
    assert_llm_base_url("")
    assert_llm_base_url("http://localhost:11434", provider="ollama")
    with pytest.raises(ValueError):
        assert_llm_base_url("http://10.0.0.5:11434", provider="ollama")


# --- the router builds every request from the validated base ------------------------------


def test_endpoint_validates_configured_urls_and_keeps_defaults() -> None:
    assert _endpoint(LLMProvider.OLLAMA, "http://localhost:11434/") == "http://localhost:11434"
    assert _endpoint(LLMProvider.OPENAI, None) == "https://api.openai.com/v1"
    assert _endpoint(LLMProvider.OPENAI_COMPATIBLE, "") == "http://localhost:1234/v1"
    with pytest.raises(ValueError):
        _endpoint(LLMProvider.OPENAI, "https://evil.example.com/v1")


def test_chat_url_refuses_unlisted_host_and_keeps_local_lm_studio_working() -> None:
    router = LLMRouter()
    router.settings = LLMConfig(
        provider=LLMProvider.OPENAI_COMPATIBLE, base_url="http://10.0.0.7:1234/v1"
    )
    with pytest.raises(ValueError, match=LLM_ALLOWED_HOSTS_ENV):
        router._chat_url()
    router.settings = LLMConfig(
        provider=LLMProvider.OPENAI_COMPATIBLE, base_url="http://127.0.0.1:1234/v1"
    )
    assert router._chat_url() == "http://127.0.0.1:1234/v1/chat/completions"
    router.settings = LLMConfig(provider=LLMProvider.OLLAMA, base_url="http://localhost:11434")
    assert router._chat_url() == "http://localhost:11434/v1/chat/completions"


@pytest.mark.asyncio
async def test_completion_never_contacts_an_unlisted_stored_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    _patch_httpx(monkeypatch, handler)
    router = LLMRouter()
    router.settings = LLMConfig(
        provider=LLMProvider.OPENAI_COMPATIBLE, model="m", base_url="http://10.0.0.7:1234/v1"
    )
    with pytest.raises(ValueError, match=LLM_ALLOWED_HOSTS_ENV):
        await router._complete_once([{"role": "user", "content": "hi"}])
    assert sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["anthropic", "openai", "openai-compatible", "ollama"])
async def test_probe_refuses_a_blocked_endpoint_without_sending_anything(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    _patch_httpx(monkeypatch, handler)
    for url in ("http://169.254.169.254/latest/meta-data", "https://evil.example.com/v1"):
        result = await LLMRouter().probe_provider(provider, url)
        assert result["ok"] is False
        assert result["status"] == "blocked"
    assert sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (None, "https://api.anthropic.com/v1/models"),
        ("https://api.anthropic.com", "https://api.anthropic.com/v1/models"),
        ("https://api.anthropic.com/v1/", "https://api.anthropic.com/v1/models"),
    ],
)
async def test_anthropic_probe_asks_a_fixed_path_on_the_validated_base(
    monkeypatch: pytest.MonkeyPatch, base_url: str | None, expected: str
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(401, json={"error": "no key"})

    _patch_httpx(monkeypatch, handler)
    result = await LLMRouter().probe_provider("anthropic", base_url)
    assert seen == [expected]
    assert result["ok"] is True
    assert result["status"] == "reachable"


@pytest.mark.asyncio
async def test_ollama_probe_asks_api_tags_on_the_validated_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})

    _patch_httpx(monkeypatch, handler)
    result = await LLMRouter().probe_provider("ollama", "http://localhost:11434/v1/")
    assert seen == ["http://localhost:11434/api/tags"]
    assert result["ok"] is True
    assert result["models"] == ["llama3.2:3b"]
    # no URL at all means the local default
    seen.clear()
    await LLMRouter().probe_provider("ollama", None)
    assert seen == ["http://127.0.0.1:11434/api/tags"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://127.0.0.1:1234/v1", "http://127.0.0.1:1234/v1/models"),
        ("http://127.0.0.1:1234", "http://127.0.0.1:1234/v1/models"),
        ("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1/models"),
    ],
)
async def test_openai_compatible_probe_lists_models_on_the_validated_base(
    monkeypatch: pytest.MonkeyPatch, base_url: str, expected: str
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"data": [{"id": "local-model"}]})

    _patch_httpx(monkeypatch, handler)
    result = await LLMRouter().probe_provider("openai-compatible", base_url)
    assert seen == [expected]
    assert result["ok"] is True
    assert result["models"] == ["local-model"]


@pytest.mark.asyncio
async def test_probe_follows_the_operator_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"data": []})

    _patch_httpx(monkeypatch, handler)
    assert (await LLMRouter().probe_provider("openai-compatible", "http://10.0.0.7:8000/v1"))[
        "status"
    ] == "blocked"
    monkeypatch.setenv(LLM_ALLOWED_HOSTS_ENV, "10.0.0.7")
    get_env.cache_clear()
    result = await LLMRouter().probe_provider("openai-compatible", "http://10.0.0.7:8000/v1")
    assert result["ok"] is True
    assert seen == ["http://10.0.0.7:8000/v1/models"]


# --- Ollama helpers ----------------------------------------------------------------------


def test_ollama_base_url_defaults_strips_v1_and_validates() -> None:
    assert ollama_base_url(None) == "http://127.0.0.1:11434"
    assert ollama_base_url("") == "http://127.0.0.1:11434"
    assert ollama_base_url("http://localhost:11434/v1/") == "http://localhost:11434"
    assert ollama_base_url("http://localhost:11434") == "http://localhost:11434"
    with pytest.raises(ValueError):
        ollama_base_url("http://10.0.0.5:11434")


@pytest.mark.asyncio
async def test_ollama_runtime_refuses_blocked_endpoint_without_sending_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"models": []})

    _patch_httpx(monkeypatch, handler)
    with pytest.raises(ValueError, match=LLM_ALLOWED_HOSTS_ENV):
        await ensure_exclusive_model("qwen2.5:3b", "http://10.0.0.5:11434")
    assert sent == []


@pytest.mark.asyncio
async def test_pull_refuses_blocked_endpoint_before_touching_job_state() -> None:
    with pytest.raises(ValueError, match=LLM_ALLOWED_HOSTS_ENV):
        await pull_jobs.start_or_attach("qwen2.5:3b", "http://10.0.0.5:11434")
    assert pull_jobs.get_job("qwen2.5:3b") is None
