"""Outbound notification dispatcher (Telegram, email, webhook, webpush, Discord, Slack)."""

from __future__ import annotations

import hashlib
import hmac
import json
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from finagent.config import get_settings, resolve_api_key
from finagent.config.schema import NotifyChannelConfig
from finagent.logging_setup import get_logger
from finagent.security.url_safety import assert_webhook_url

log = get_logger(__name__)


def _in_quiet_hours(tz_name: str, start: str | None, end: str | None) -> bool:
    if not start or not end:
        return False
    try:
        now = datetime.now(ZoneInfo(tz_name)).time()
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        from datetime import time as dtime

        st, et = dtime(sh, sm), dtime(eh, em)
        if st <= et:
            return st <= now <= et
        return now >= st or now <= et
    except Exception:
        return False


def _event_allowed(kind: str) -> bool:
    n = get_settings().notifications
    if kind == "alert":
        return n.events_alert
    if kind == "job":
        return n.events_job
    if kind == "order":
        return n.events_order
    return n.events_system


async def _send_telegram(ch: NotifyChannelConfig, title: str, body: str) -> dict[str, Any]:
    token = resolve_api_key(ch.bot_token_secret or "TELEGRAM_BOT_TOKEN")
    chat_id = ch.chat_id
    if not token or not chat_id:
        return {"ok": False, "error": "Telegram bot token or chat id missing"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    assert_webhook_url("https://api.telegram.org/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            url,
            json={"chat_id": chat_id, "text": f"{title}\n\n{body}"[:4000]},
        )
        if resp.status_code >= 400:
            return {"ok": False, "error": resp.text[:200]}
    return {"ok": True, "channel": "telegram"}


async def _send_email(ch: NotifyChannelConfig, title: str, body: str) -> dict[str, Any]:
    host = ch.smtp_host
    to_addr = ch.smtp_to
    from_addr = ch.smtp_from or to_addr
    user = resolve_api_key(ch.smtp_user_secret or "SMTP_USER")
    password = resolve_api_key(ch.smtp_password_secret or "SMTP_PASSWORD")
    if not host or not to_addr or not from_addr:
        return {"ok": False, "error": "SMTP host/from/to required"}
    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    try:
        if ch.smtp_use_tls:
            with smtplib.SMTP(host, ch.smtp_port, timeout=30) as smtp:
                smtp.starttls()
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, ch.smtp_port, timeout=30) as smtp:
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "channel": "email"}


async def _send_webhook(
    ch: NotifyChannelConfig, title: str, body: str, *, channel: str
) -> dict[str, Any]:
    secret_name = ch.webhook_url_secret or {
        "webhook": "NOTIFY_WEBHOOK_URL",
        "discord": "DISCORD_WEBHOOK_URL",
        "slack": "SLACK_WEBHOOK_URL",
    }.get(channel, "NOTIFY_WEBHOOK_URL")
    url = resolve_api_key(secret_name)
    if not url:
        return {"ok": False, "error": f"Missing webhook URL secret {secret_name}"}
    try:
        assert_webhook_url(url)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    payload: dict[str, Any]
    if channel == "discord":
        payload = {"content": f"**{title}**\n{body}"[:1900]}
    elif channel == "slack":
        payload = {"text": f"*{title}*\n{body}"}
    else:
        payload = {"title": title, "body": body, "source": "finagent"}
    headers = {"Content-Type": "application/json"}
    raw = json.dumps(payload).encode()
    hmac_key = resolve_api_key(ch.webhook_hmac_secret) if ch.webhook_hmac_secret else None
    if hmac_key:
        sig = hmac.new(hmac_key.encode(), raw, hashlib.sha256).hexdigest()
        headers["X-FinAgent-Signature"] = sig
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, content=raw, headers=headers)
        if resp.status_code >= 400:
            return {"ok": False, "error": resp.text[:200]}
    return {"ok": True, "channel": channel}


async def _send_webpush(ch: NotifyChannelConfig, title: str, body: str) -> dict[str, Any]:
    # Subscriptions stored as secret JSON list optional; without pywebpush just report configured
    pub = ch.vapid_public_key
    priv = resolve_api_key(ch.vapid_private_secret or "VAPID_PRIVATE_KEY")
    if not pub or not priv:
        return {"ok": False, "error": "Generate VAPID keys in Settings → Notifications first"}
    # Best-effort: if pywebpush + subscriptions exist
    subs_raw = resolve_api_key("WEBPUSH_SUBSCRIPTIONS_JSON")
    if not subs_raw:
        return {
            "ok": True,
            "channel": "webpush",
            "note": "VAPID ready — open the app on your phone and allow push to register a subscription",
        }
    try:
        from pywebpush import webpush

        subs = json.loads(subs_raw)
        if not isinstance(subs, list):
            subs = [subs]
        for sub in subs:
            webpush(
                subscription_info=sub,
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=priv,
                vapid_claims={"sub": ch.vapid_mailto or "mailto:finagent@localhost"},
            )
    except ImportError:
        return {"ok": False, "error": "Install pywebpush for browser push delivery"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "channel": "webpush"}


async def dispatch_notification(
    *,
    kind: str,
    title: str,
    body: str,
    symbol: str | None = None,
    channels: list[str] | None = None,
) -> dict[str, Any]:
    """Fan-out to enabled channels. Always safe to call (no-op if master off)."""
    settings = get_settings()
    n = settings.notifications
    results: list[dict[str, Any]] = []
    if not n.master_enabled:
        return {"ok": True, "skipped": "master_disabled", "results": results}
    if not _event_allowed(kind):
        return {"ok": True, "skipped": "event_filtered", "results": results}
    if symbol and symbol.upper() in {s.upper() for s in n.mute_symbols}:
        return {"ok": True, "skipped": "muted_symbol", "results": results}
    if _in_quiet_hours(settings.appearance.timezone, n.quiet_hours_start, n.quiet_hours_end):
        return {"ok": True, "skipped": "quiet_hours", "results": results}

    wanted = set(channels or ["telegram", "email", "webhook", "webpush", "discord", "slack"])
    mapping = {
        "telegram": (n.telegram, _send_telegram),
        "email": (n.email, _send_email),
        "webhook": (n.webhook, lambda c, t, b: _send_webhook(c, t, b, channel="webhook")),
        "discord": (n.discord, lambda c, t, b: _send_webhook(c, t, b, channel="discord")),
        "slack": (n.slack, lambda c, t, b: _send_webhook(c, t, b, channel="slack")),
        "webpush": (n.webpush, _send_webpush),
    }
    for name in wanted:
        ch, sender = mapping.get(name, (None, None))
        if not ch or not sender or not ch.enabled:
            continue
        try:
            results.append(await sender(ch, title, body))
        except Exception as exc:
            log.warning("notify_channel_failed", channel=name, error=str(exc))
            results.append({"ok": False, "channel": name, "error": str(exc)})
    return {"ok": any(r.get("ok") for r in results) if results else True, "results": results}


async def test_channel(channel: str) -> dict[str, Any]:
    return await dispatch_notification(
        kind="system",
        title="FinAgent test",
        body=f"Test message for {channel}. If you see this, notifications work.",
        channels=[channel],
    )
