"""OpenAI-compatible LLM router (httpx) with small-model JSON tool fallback.

Covers Ollama, LM Studio, OpenAI, OpenRouter, Groq, and any OpenAI-compatible
endpoint without pulling the heavy LiteLLM dependency.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from finagent.config import get_settings, resolve_api_key
from finagent.config.schema import LLMProvider, ToolMode
from finagent.logging_setup import get_logger

log = get_logger(__name__)

JSON_TOOL_SYSTEM = """You are FinAgent, a careful finance assistant.
You MUST use only numbers that come from tool results and cite source + timestamp.
When you need data or actions, reply with ONLY a JSON object:
{"tool":"<name>","arguments":{...}}
When you can answer the user, reply with ONLY:
{"final":"<your markdown answer>"}
Never invent prices. Never enable live trading or change settings.
Not financial advice.
"""


def parse_json_tool_payload(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None


def truncate_messages(messages: list[dict[str, Any]], max_tokens: int) -> list[dict[str, Any]]:
    budget = max_tokens * 4
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    kept: list[dict[str, Any]] = []
    used = sum(len(str(m.get("content", ""))) for m in system)
    for m in reversed(rest):
        size = len(str(m.get("content", "")))
        if used + size > budget and kept:
            break
        kept.insert(0, m)
        used += size
    return [*system, *kept]


def _api_key_for(provider: LLMProvider, explicit_ref: str | None) -> str | None:
    if explicit_ref:
        return resolve_api_key(explicit_ref)
    mapping = {
        LLMProvider.OPENAI: "OPENAI_API_KEY",
        LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
        LLMProvider.OPENROUTER: "OPENROUTER_API_KEY",
        LLMProvider.GROQ: "GROQ_API_KEY",
        LLMProvider.OPENAI_COMPATIBLE: "OPENAI_API_KEY",
        LLMProvider.OLLAMA: None,
        LLMProvider.DEMO: None,
    }
    ref = mapping.get(provider)
    return resolve_api_key(ref) if ref else None


def _endpoint(provider: LLMProvider, base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")
    defaults = {
        LLMProvider.OLLAMA: "http://localhost:11434",
        LLMProvider.OPENAI: "https://api.openai.com/v1",
        LLMProvider.OPENROUTER: "https://openrouter.ai/api/v1",
        LLMProvider.GROQ: "https://api.groq.com/openai/v1",
        LLMProvider.ANTHROPIC: "https://api.anthropic.com/v1",
        LLMProvider.OPENAI_COMPATIBLE: "http://localhost:1234/v1",
        LLMProvider.DEMO: "",
    }
    return defaults[provider]


def _demo_complete(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Built-in agent brain — no external LLM required."""
    last_user = ""
    last_tool = ""
    for m in reversed(messages):
        role = m.get("role")
        content = str(m.get("content") or "")
        if role == "user" and content.startswith("Tool result:") and not last_tool:
            last_tool = content
        if role == "user" and not content.startswith("Tool result:") and not last_user:
            last_user = content
        if last_user and (last_tool or role == "user"):
            break

    # After a tool result, summarize
    if last_tool:
        try:
            payload = json.loads(last_tool.replace("Tool result:", "", 1).strip().split("\n")[0])
        except Exception:
            payload = {"raw": last_tool}
        result = payload.get("result") if isinstance(payload, dict) else payload
        return {
            "content": json.dumps(
                {
                    "final": (
                        "Here is what I found from live tools (demo LLM mode).\n\n"
                        f"```json\n{json.dumps(result, indent=2)[:3500]}\n```\n\n"
                        "_Not financial advice. Switch to Ollama or a cloud model in Settings "
                        "for richer natural-language analysis._"
                    )
                }
            ),
            "tool_calls": [],
            "raw": {"provider": "demo"},
        }

    text = last_user.lower()
    # Detect symbol-ish tokens
    symbol_match = re.search(
        r"\b([A-Z]{1,10}(?:\.NS|\.BO)?|[A-Z]{2,10}/USDT|MF:\d+|BTC|ETH|AAPL|MSFT|GOOGL|RELIANCE|TCS|INFY)\b",
        last_user,
        re.I,
    )
    symbol = symbol_match.group(1).upper() if symbol_match else None
    if symbol in {"BTC", "ETH"}:
        symbol = f"{symbol}/USDT"
    if symbol == "RELIANCE":
        symbol = "RELIANCE.NS"
    if symbol == "TCS":
        symbol = "TCS.NS"
    if symbol == "INFY":
        symbol = "INFY.NS"

    if any(w in text for w in ("buy", "sell", "paper-buy", "paper buy", "paper trade")):
        side = "sell" if "sell" in text else "buy"
        qty_match = re.search(r"\b(\d+(?:\.\d+)?)\b", last_user)
        qty = qty_match.group(1) if qty_match else "1"
        return {
            "content": json.dumps(
                {
                    "tool": "place_paper_order",
                    "arguments": {
                        "symbol": symbol or "AAPL",
                        "side": side,
                        "quantity": qty,
                        "price": "0",
                        "asset_class": "crypto" if symbol and "/" in symbol else "equity",
                        "confirmed": False,
                    },
                }
            ),
            "tool_calls": [],
            "raw": {"provider": "demo"},
        }
    if any(w in text for w in ("portfolio", "holdings", "my positions", "p&l", "pnl", "analyze my")):
        return {
            "content": json.dumps({"tool": "get_portfolio", "arguments": {}}),
            "tool_calls": [],
            "raw": {"provider": "demo"},
        }
    if any(w in text for w in ("top mover", "movers", "top moves")):
        return {
            "content": json.dumps({"tool": "run_screener", "arguments": {"universe": "watchlist"}}),
            "tool_calls": [],
            "raw": {"provider": "demo"},
        }
    if any(w in text for w in ("option", "options", "chain", "ce", "pe")) and symbol:
        return {
            "content": json.dumps({"tool": "get_option_chain", "arguments": {"symbol": symbol}}),
            "tool_calls": [],
            "raw": {"provider": "demo"},
        }
    if any(w in text for w in ("screen", "screener", "ideas", "watch")):
        universe = "crypto_majors" if "crypto" in text else "india_bluechips" if "india" in text else "watchlist"
        return {
            "content": json.dumps({"tool": "run_screener", "arguments": {"universe": universe}}),
            "tool_calls": [],
            "raw": {"provider": "demo"},
        }
    if symbol or any(w in text for w in ("quote", "price", "nav", "how much")):
        return {
            "content": json.dumps(
                {"tool": "get_quote", "arguments": {"symbol": symbol or "AAPL"}}
            ),
            "tool_calls": [],
            "raw": {"provider": "demo"},
        }
    if any(w in text for w in ("search", "find")):
        q = last_user.split(" ", 1)[-1] if " " in last_user else "NIFTY"
        return {
            "content": json.dumps({"tool": "search_symbols", "arguments": {"query": q}}),
            "tool_calls": [],
            "raw": {"provider": "demo"},
        }

    return {
        "content": json.dumps(
            {
                "final": (
                    "I'm FinAgent in **Demo mode** (works with zero setup).\n\n"
                    "Try asking:\n"
                    "- `What's the quote for RELIANCE.NS?`\n"
                    "- `Show my portfolio`\n"
                    "- `Run india screener`\n"
                    "- `Price of BTC/USDT`\n\n"
                    "When you're ready for richer chat, open **Settings → AI / LLMs** and pick "
                    "Ollama (free/local finance models) or a cloud provider.\n\n"
                    "_Not financial advice._"
                )
            }
        ),
        "tool_calls": [],
        "raw": {"provider": "demo"},
    }


class LLMRouter:
    def __init__(self) -> None:
        self.settings = get_settings().llm

    def refresh(self) -> None:
        self.settings = get_settings().llm
        self.settings.ensure_profiles()
        self.settings.sync_legacy_from_active()

    def apply_profile(self, profile_id: str | None = None) -> None:
        """Point legacy fields at a specific profile (active / chat / analysis)."""
        self.refresh()
        profile = self.settings.get_profile(profile_id)
        self.settings.provider = profile.provider
        self.settings.model = profile.model
        self.settings.base_url = profile.base_url
        self.settings.api_key_ref = profile.api_key_name
        self.settings.tool_mode = profile.tool_mode
        self.settings.timeout_s = profile.timeout_s
        self.settings.max_context_tokens = profile.max_context_tokens
        self.settings.temperature = profile.temperature

    def effective_tool_mode(self) -> ToolMode:
        if self.settings.provider == LLMProvider.DEMO:
            return ToolMode.JSON_FALLBACK
        mode = self.settings.tool_mode
        if mode != ToolMode.AUTO:
            return mode
        model = self.settings.model.lower()
        tiny_markers = ("3b", "1b", "2b", "phi", "tiny", "mini", "gemma:2b")
        if any(m in model for m in tiny_markers):
            return ToolMode.JSON_FALLBACK
        return ToolMode.NATIVE

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key = _api_key_for(self.settings.provider, self.settings.api_key_ref)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if self.settings.provider == LLMProvider.OPENROUTER:
            headers["HTTP-Referer"] = "https://github.com/finagent/finagent"
            headers["X-Title"] = "FinAgent"
        if self.settings.provider == LLMProvider.ANTHROPIC and key:
            headers["x-api-key"] = key
            headers["anthropic-version"] = "2023-06-01"
            headers.pop("Authorization", None)
        return headers

    def _chat_url(self) -> str:
        base = _endpoint(self.settings.provider, self.settings.base_url)
        if self.settings.provider == LLMProvider.OLLAMA:
            # Prefer OpenAI-compatible endpoint shipped by modern Ollama
            if base.endswith("/v1"):
                return f"{base}/chat/completions"
            return f"{base}/v1/chat/completions"
        if self.settings.provider == LLMProvider.ANTHROPIC:
            return f"{base}/messages"
        return f"{base}/chat/completions"

    def _normalize_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role", "user")
            if role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.get("tool_call_id", "tool"),
                        "content": m.get("content", ""),
                    }
                )
            else:
                item: dict[str, Any] = {"role": role, "content": m.get("content") or ""}
                if m.get("tool_calls"):
                    item["tool_calls"] = m["tool_calls"]
                out.append(item)
        return out

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True
    )
    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        model_override: str | None = None,
        stream: bool = False,
        profile_id: str | None = None,
        allow_fallback: bool = True,
    ) -> dict[str, Any]:
        tried_id = profile_id or self.settings.chat_profile_id or self.settings.active_profile_id
        self.apply_profile(tried_id)
        try:
            return await self._complete_once(
                messages, tools=tools, model_override=model_override
            )
        except Exception as primary_exc:
            fb = self.settings.fallback_profile_id
            if not allow_fallback or not fb or fb == tried_id:
                raise
            log.warning("llm_primary_failed_trying_fallback", error=str(primary_exc), fallback=fb)
            self.apply_profile(fb)
            return await self._complete_once(
                messages, tools=tools, model_override=model_override
            )

    async def _complete_once(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        if self.settings.provider == LLMProvider.DEMO:
            return _demo_complete(messages)
        model = model_override or self.settings.chat_model or self.settings.model
        msgs = truncate_messages(
            self._normalize_messages(messages), self.settings.max_context_tokens
        )
        mode = self.effective_tool_mode()

        if self.settings.provider == LLMProvider.ANTHROPIC:
            return await self._complete_anthropic(
                msgs, model=model, tools=tools if mode == ToolMode.NATIVE else None
            )

        payload: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "temperature": self.settings.temperature,
            "stream": False,
        }
        if tools and mode == ToolMode.NATIVE:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        timeout = httpx.Timeout(self.settings.timeout_s)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(self._chat_url(), headers=self._headers(), json=payload)
            if resp.status_code >= 400:
                if self.settings.provider == LLMProvider.OLLAMA:
                    return await self._complete_ollama_native(msgs, model=model, client=client)
                resp.raise_for_status()
            data = resp.json()

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            tool_calls.append(
                {
                    "id": tc.get("id", "call"),
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", "{}"),
                }
            )
        return {"content": message.get("content") or "", "tool_calls": tool_calls, "raw": data}

    async def _complete_ollama_native(
        self, messages: list[dict[str, Any]], *, model: str, client: httpx.AsyncClient
    ) -> dict[str, Any]:
        base = _endpoint(self.settings.provider, self.settings.base_url).replace("/v1", "")
        payload = {
            "model": model,
            "messages": [{"role": m["role"], "content": m.get("content") or ""} for m in messages],
            "stream": False,
            "options": {"temperature": self.settings.temperature},
        }
        resp = await client.post(f"{base}/api/chat", headers=self._headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("message") or {}
        return {"content": msg.get("content") or "", "tool_calls": [], "raw": data}

    async def _complete_anthropic(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        system = "\n".join(m["content"] for m in messages if m.get("role") == "system")
        converted = []
        for m in messages:
            if m.get("role") == "system":
                continue
            converted.append(
                {
                    "role": "assistant" if m["role"] == "assistant" else "user",
                    "content": m.get("content") or "",
                }
            )
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": 2048,
            "temperature": self.settings.temperature,
            "messages": converted or [{"role": "user", "content": "hello"}],
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                }
                for t in tools
                if t.get("type") == "function"
            ]
        timeout = httpx.Timeout(self.settings.timeout_s)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(self._chat_url(), headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        text_parts = []
        tool_calls = []
        for block in data.get("content") or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id", "call"),
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input") or {}),
                    }
                )
        return {"content": "".join(text_parts), "tool_calls": tool_calls, "raw": data}

    async def stream_tokens(
        self,
        messages: list[dict[str, Any]],
        *,
        model_override: str | None = None,
    ) -> AsyncIterator[str]:
        # Simple non-stream fallback chunking for compatibility
        result = await self.complete(messages, model_override=model_override)
        content = result.get("content") or ""
        size = 32
        for i in range(0, len(content), size):
            yield content[i : i + size]

    async def test_connection(self) -> dict[str, Any]:
        self.refresh()
        return await self.test_profile(None)

    async def test_profile(self, profile_id: str | None) -> dict[str, Any]:
        self.apply_profile(profile_id)
        if self.settings.provider == LLMProvider.DEMO:
            return {
                "ok": True,
                "sample": "ok (demo mode - no external LLM)",
                "tool_mode": ToolMode.JSON_FALLBACK.value,
                "provider": "demo",
                "model": "demo",
            }
        try:
            result = await self._complete_once(
                [
                    {"role": "system", "content": "Reply with exactly: ok"},
                    {"role": "user", "content": "ping"},
                ]
            )
            return {
                "ok": True,
                "sample": (result.get("content") or "")[:200],
                "tool_mode": self.effective_tool_mode().value,
                "provider": self.settings.provider.value,
                "model": self.settings.model,
            }
        except Exception as exc:
            log.warning("llm_test_failed", error=str(exc))
            return {
                "ok": False,
                "error": str(exc),
                "provider": self.settings.provider.value,
                "model": self.settings.model,
            }

    async def probe_provider(
        self, provider: str, base_url: str | None = None, api_key_name: str | None = None
    ) -> dict[str, Any]:
        """Check if a provider endpoint is reachable (before saving a profile)."""
        from finagent.llm.catalog import get_provider

        meta = get_provider(provider)
        if provider == "demo":
            return {"ok": True, "status": "ready", "message": "Demo is always available"}
        url = base_url or (meta or {}).get("default_base_url") or ""
        try:
            if provider == "ollama":
                base = (url or "http://127.0.0.1:11434").replace("/v1", "").rstrip("/")
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(f"{base}/api/tags")
                    resp.raise_for_status()
                    models = [m.get("name") for m in resp.json().get("models", []) if m.get("name")]
                    return {
                        "ok": True,
                        "status": "online",
                        "message": f"Ollama online · {len(models)} model(s)",
                        "models": models,
                    }
            # OpenAI-compatible style probe
            headers = {"Content-Type": "application/json"}
            key = resolve_api_key(api_key_name or (meta or {}).get("secret_name"))
            if key:
                headers["Authorization"] = f"Bearer {key}"
            if provider == "anthropic":
                base = (url or "https://api.anthropic.com").rstrip("/")
                if key:
                    headers = {
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    }
                async with httpx.AsyncClient(timeout=6.0) as client:
                    # lightweight: list models not always available; ping with empty fails — just check TLS/host
                    resp = await client.get(base, headers=headers)
                    return {
                        "ok": resp.status_code < 500,
                        "status": "reachable" if resp.status_code < 500 else "error",
                        "message": f"Anthropic reachable (HTTP {resp.status_code})",
                    }
            base = url.rstrip("/")
            if not base.endswith("/v1"):
                # many providers already include /v1
                models_url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
            else:
                models_url = f"{base}/models"
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(models_url, headers=headers)
                if resp.status_code >= 400:
                    return {
                        "ok": False,
                        "status": "auth_or_unreachable",
                        "message": f"HTTP {resp.status_code}: {resp.text[:200]}",
                    }
                data = resp.json()
                models = []
                for m in data.get("data") or []:
                    mid = m.get("id")
                    if mid:
                        models.append(mid)
                return {
                    "ok": True,
                    "status": "online",
                    "message": f"Online · {len(models)} model(s) listed",
                    "models": models[:80],
                }
        except Exception as exc:
            return {"ok": False, "status": "offline", "message": str(exc)}

    async def list_models(
        self, provider: str, base_url: str | None = None, api_key_name: str | None = None
    ) -> list[str]:
        probe = await self.probe_provider(provider, base_url, api_key_name)
        return list(probe.get("models") or [])

    async def pull_ollama_model(self, model: str, base_url: str | None = None) -> dict[str, Any]:
        """Ask local Ollama to pull a model (may take minutes)."""
        base = (base_url or self.settings.base_url or "http://127.0.0.1:11434").replace("/v1", "").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
                resp = await client.post(f"{base}/api/pull", json={"name": model, "stream": False})
                if resp.status_code >= 400:
                    return {"ok": False, "error": resp.text[:500]}
                return {"ok": True, "model": model, "detail": resp.json()}
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "hint": "Is Ollama running? Install from https://ollama.com/download then retry.",
            }

    async def list_ollama_models(self) -> list[str]:
        base = _endpoint(LLMProvider.OLLAMA, self.settings.base_url).replace("/v1", "")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception as exc:
            log.info("ollama_list_failed", error=str(exc))
            return []


_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
