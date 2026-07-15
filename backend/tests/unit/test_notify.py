"""Notification dispatcher unit tests."""

from __future__ import annotations

import pytest

from finagent.config.schema import AppSettings
from finagent.notify.dispatcher import dispatch_notification


@pytest.mark.asyncio
async def test_dispatch_skipped_when_master_off(monkeypatch):
    settings = AppSettings()
    settings.notifications.master_enabled = False
    monkeypatch.setattr("finagent.notify.dispatcher.get_settings", lambda: settings)
    out = await dispatch_notification(kind="alert", title="t", body="b")
    assert out.get("skipped") == "master_disabled"
