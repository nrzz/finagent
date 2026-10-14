"""URL safety for LLM / Ollama endpoints and notification webhooks (SSRF mitigation)."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from functools import lru_cache
from urllib.parse import urlparse, urlsplit

from finagent.config import get_env

#: Operator setting (environment variable or ``.env`` entry) that extends the LLM endpoint
#: allow-list with extra hosts. Read SECURITY.md before using it.
LLM_ALLOWED_HOSTS_ENV = "FINAGENT_LLM_ALLOWED_HOSTS"

# Known cloud LLM API hosts. HTTPS only; a subdomain of one of these is accepted as well.
_CLOUD_HOSTS = frozenset(
    {
        "api.openai.com",
        "api.anthropic.com",
        "openrouter.ai",
        "api.groq.com",
        "generativelanguage.googleapis.com",
    }
)

# Cloud metadata services. Never allowed, not even through FINAGENT_LLM_ALLOWED_HOSTS.
_METADATA_HOSTS = frozenset({"metadata.google.internal", "metadata"})

_MAX_URL_LENGTH = 2048
_HOST_LABEL_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_")
_PATH_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~/")

_IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _host_literal(host: str) -> _IPAddress | None:
    """Return the IP address ``host`` spells out, or None if it is not an IP literal."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _unmap(ip: _IPAddress) -> _IPAddress:
    """Judge IPv4-mapped IPv6 addresses (``::ffff:a.b.c.d``) by the IPv4 address inside."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _is_valid_hostname(host: str) -> bool:
    """Strict DNS-name check: ASCII letters, digits, ``-`` and ``_``; labels of 1-63 chars."""
    if not host or len(host) > 253:
        return False
    for label in host.split("."):
        if not 1 <= len(label) <= 63 or label[0] == "-" or label[-1] == "-":
            return False
        if not _HOST_LABEL_CHARS.issuperset(label):
            return False
    return True


def _is_cloud_host(host: str) -> bool:
    return any(host == known or host.endswith(f".{known}") for known in _CLOUD_HOSTS)


def _is_safe_path(path: str) -> bool:
    """A base-URL path prefix such as ``/v1``: plain segments only, no ``.``/``..``/empty ones."""
    if not path.startswith("/") or not _PATH_CHARS.issuperset(path):
        return False
    return all(segment not in ("", ".", "..") for segment in path[1:].split("/"))


@lru_cache(maxsize=16)
def _parse_allowed_hosts(raw: str) -> tuple[frozenset[str], frozenset[_IPAddress]]:
    """Split the operator's comma-separated host list into DNS names and IP addresses.

    Entries are hosts only; a pasted ``host:port`` or full URL is reduced to its host. Anything
    that is not a valid host name or IP address is ignored.
    """
    names: set[str] = set()
    ips: set[_IPAddress] = set()
    for entry in raw.split(","):
        item = entry.strip().lower()
        if not item:
            continue
        literal = _host_literal(item.strip("[]"))
        if literal is None:
            try:
                parsed = urlsplit(item if "://" in item else f"//{item}")
                host = (parsed.hostname or "").removesuffix(".")
            except ValueError:
                continue
            literal = _host_literal(host)
            if literal is None:
                if _is_valid_hostname(host):
                    names.add(host)
                continue
        ips.add(_unmap(literal))
    return frozenset(names), frozenset(ips)


def _not_allowed_message(host: str) -> str:
    return (
        f"Host '{host}' is not allowed for LLM endpoints. By default only localhost "
        "(127.0.0.1, [::1]) and the known HTTPS cloud providers are accepted. To use another "
        f"machine, the server operator must list it in {LLM_ALLOWED_HOSTS_ENV} (see SECURITY.md)."
    )


def validate_llm_base_url(url: str, *, allowed_hosts: Iterable[str] | None = None) -> str:
    """Validate an LLM / Ollama endpoint and return its canonical base URL.

    Every outbound LLM request is built from the string returned here plus a fixed path, never
    from the raw value somebody typed into a form or an API call. Rules:

    * the scheme is ``http`` or ``https``; no ``user:password@``, query string or fragment, and
      only plain path segments (``/v1``, ``/openai/v1``)
    * the host is ``localhost`` / a loopback address, a known cloud API host (HTTPS only), or a
      host the operator listed in ``FINAGENT_LLM_ALLOWED_HOSTS``
    * link-local, metadata, unspecified, multicast and reserved addresses are refused even when
      listed

    Raises ``ValueError`` with a user-readable reason when the URL is refused. ``allowed_hosts``
    overrides the operator setting (used by tests).
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("Endpoint URL is empty")
    if len(raw) > _MAX_URL_LENGTH:
        raise ValueError("Endpoint URL is too long")
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise ValueError("Endpoint URL must not contain spaces or control characters")
    if "://" not in raw:
        raise ValueError("Endpoint URL must start with http:// or https://")
    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise ValueError("Endpoint URL is not valid") from exc
    if parts.scheme not in ("http", "https"):
        raise ValueError("Endpoint URL must start with http:// or https://")
    if "@" in parts.netloc:
        raise ValueError("Endpoint URL must not contain a username or password")
    if parts.query or parts.fragment or "?" in raw or "#" in raw:
        raise ValueError("Endpoint URL must not contain a query string or fragment")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("Endpoint URL has an invalid port") from exc
    if port == 0:
        raise ValueError("Endpoint URL has an invalid port")
    host = (parts.hostname or "").removesuffix(".")
    if not host:
        raise ValueError("Endpoint URL has no host")
    path = parts.path.rstrip("/")
    if path and not _is_safe_path(path):
        raise ValueError("Endpoint URL path may only contain plain segments such as /v1")

    if allowed_hosts is None:
        allowed_names, allowed_ips = _parse_allowed_hosts(get_env().llm_allowed_hosts)
    else:
        allowed_names, allowed_ips = _parse_allowed_hosts(",".join(allowed_hosts))

    literal = _host_literal(host)
    if literal is not None:
        ip = _unmap(literal)
        if not ip.is_loopback:
            if ip.is_unspecified or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                raise ValueError(
                    f"Address {host} is blocked: link-local, metadata, multicast and "
                    "unspecified addresses are never allowed for LLM endpoints"
                )
            if ip not in allowed_ips:
                raise ValueError(_not_allowed_message(host))
        host_text = f"[{literal.compressed}]" if literal.version == 6 else literal.compressed
    else:
        if not _is_valid_hostname(host):
            raise ValueError("Endpoint URL has an invalid host name")
        if host in _METADATA_HOSTS:
            raise ValueError(f"Host '{host}' is a cloud metadata service and is blocked")
        if _is_cloud_host(host):
            if parts.scheme != "https":
                raise ValueError("Cloud LLM endpoints must use HTTPS")
        elif host != "localhost" and host not in allowed_names:
            raise ValueError(_not_allowed_message(host))
        host_text = host

    scheme = "https" if parts.scheme == "https" else "http"
    netloc = host_text if port is None else f"{host_text}:{port}"
    return f"{scheme}://{netloc}{path}"


def is_safe_llm_base_url(url: str | None) -> tuple[bool, str]:
    """Non-raising form of :func:`validate_llm_base_url`; an empty URL means "use the default"."""
    if not url:
        return True, "ok"
    try:
        validate_llm_base_url(url)
    except ValueError as exc:
        return False, str(exc)
    return True, "ok"


def assert_llm_base_url(url: str | None, *, provider: str = "") -> None:
    """Raise ``ValueError`` if ``url`` may not be used as an LLM endpoint (empty is fine)."""
    if url:
        validate_llm_base_url(url)


def is_safe_webhook_url(url: str | None, *, allow_private: bool = False) -> tuple[bool, str]:
    """SSRF guard for notification webhooks (Telegram API hosts allowed; private IPs blocked)."""
    if not url:
        return False, "Missing webhook URL"
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in ("https", "http"):
        return False, "Webhook must be http(s)"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "Missing host"
    if host in ("169.254.169.254", "metadata.google.internal"):
        return False, "Blocked metadata host"
    # Well-known public notify hosts
    allowed_hosts = {
        "api.telegram.org",
        "discord.com",
        "discordapp.com",
        "hooks.slack.com",
    }
    if host in allowed_hosts or any(host.endswith(f".{h}") for h in allowed_hosts):
        if parsed.scheme != "https":
            return False, "Notify hosts must use HTTPS"
        return True, "ok"
    try:
        infos = socket.getaddrinfo(
            host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        return False, f"Cannot resolve host {host}"
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, f"Blocked address {ip_str}"
        if ip.is_private and not allow_private:
            return (
                False,
                f"Private webhook URLs blocked ({ip_str}). Set FINAGENT_ALLOW_PRIVATE_WEBHOOKS=1 only on trusted LAN.",
            )
    if parsed.scheme != "https" and not allow_private:
        return False, "Public webhooks must use HTTPS"
    return True, "ok"


def assert_webhook_url(url: str | None) -> None:
    import os

    allow_private = os.environ.get("FINAGENT_ALLOW_PRIVATE_WEBHOOKS", "").lower() in (
        "1",
        "true",
        "yes",
    )
    ok, reason = is_safe_webhook_url(url, allow_private=allow_private)
    if not ok:
        raise ValueError(reason)
