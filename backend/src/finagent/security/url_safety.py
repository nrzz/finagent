"""URL safety for LLM / Ollama base URLs (SSRF mitigation)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def is_safe_llm_base_url(url: str | None) -> tuple[bool, str]:
    """Allow localhost + private LAN; block link-local / metadata / public cloud by default."""
    if not url:
        return True, "ok"
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "Missing host"
    if host in ("localhost", "127.0.0.1", "::1"):
        return True, "ok"
    # Block obvious cloud metadata
    if host in ("169.254.169.254", "metadata.google.internal"):
        return False, "Blocked metadata host"
    try:
        infos = socket.getaddrinfo(host, parsed.port or 80, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False, f"Cannot resolve host {host}"
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_loopback or ip.is_private:
            continue
        if ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, f"Blocked address {ip_str}"
        # Public IP — deny for Ollama-style local tooling (cloud providers use known HTTPS hosts)
        if parsed.scheme in ("http",) and not ip.is_private and not ip.is_loopback:
            # Allow well-known API hosts over https only
            return False, f"Public HTTP endpoint not allowed ({ip_str}). Use HTTPS cloud providers or localhost."
    return True, "ok"


# Known cloud LLM API hosts (HTTPS)
_CLOUD_HOSTS = {
    "api.openai.com",
    "api.anthropic.com",
    "openrouter.ai",
    "api.groq.com",
    "generativelanguage.googleapis.com",
}


def assert_llm_base_url(url: str | None, *, provider: str = "") -> None:
    if not url:
        return
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = (parsed.hostname or "").lower()
    if host in _CLOUD_HOSTS or any(host.endswith(f".{h}") for h in _CLOUD_HOSTS):
        if parsed.scheme != "https":
            raise ValueError("Cloud LLM endpoints must use HTTPS")
        return
    ok, reason = is_safe_llm_base_url(url)
    if not ok:
        raise ValueError(reason)
