"""APScheduler jobs: alerts, analysis reminders, DCA paper buys."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from finagent.data import get_market_registry
from finagent.logging_setup import get_logger
from finagent.portfolio.money import D
from finagent.trading import get_paper_broker

log = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None
_alert_rules: list[dict[str, Any]] = []
_job_defs: list[dict[str, Any]] = []


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def scan_alerts() -> dict[str, Any]:
    triggered: list[dict[str, Any]] = []
    for rule in list(_alert_rules):
        if not rule.get("active", True):
            continue
        try:
            q = await get_market_registry().get_quote(rule["symbol"])
            thr = D(rule["threshold"])
            cond = rule["condition"]
            hit = (cond == "above" and q.price >= thr) or (cond == "below" and q.price <= thr)
            if hit:
                event = {
                    "symbol": rule["symbol"],
                    "condition": cond,
                    "threshold": str(thr),
                    "price": str(q.price),
                    "as_of": q.as_of.isoformat(),
                    "source": q.source,
                }
                triggered.append(event)
                rule["last_triggered_at"] = datetime.now(UTC).isoformat()
                log.info("alert_triggered", **event)
        except Exception as exc:
            log.warning("alert_scan_error", error=str(exc), symbol=rule.get("symbol"))
    return {"triggered": triggered, "scanned": len(_alert_rules)}


async def run_dca_job(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = payload.get("symbol", "BTC/USDT")
    quantity = payload.get("quantity", "0.001")
    asset_class = payload.get("asset_class", "crypto")
    q = await get_market_registry().get_quote(symbol)
    order = get_paper_broker().place_order(
        symbol=symbol,
        side="buy",
        quantity=quantity,
        price=str(q.price),
        asset_class=asset_class,
        force_open_market=True,
        meta={"job": "dca", "source": q.source, "as_of": q.as_of.isoformat()},
    )
    return order.to_dict()


async def scheduled_analysis_stub(payload: dict[str, Any]) -> dict[str, Any]:
    symbols = payload.get("symbols") or ["RELIANCE.NS", "BTC/USDT"]
    quotes = []
    for s in symbols:
        try:
            q = await get_market_registry().get_quote(s)
            quotes.append(q.to_dict())
        except Exception as exc:
            quotes.append({"symbol": s, "error": str(exc)})
    return {
        "type": "analysis_snapshot",
        "quotes": quotes,
        "note": "Wire to agent for narrative in UI",
    }


def add_alert(symbol: str, condition: str, threshold: str) -> dict[str, Any]:
    rule = {
        "id": len(_alert_rules) + 1,
        "symbol": symbol.upper(),
        "condition": condition,
        "threshold": threshold,
        "active": True,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _alert_rules.append(rule)
    return rule


def list_alerts() -> list[dict[str, Any]]:
    return list(_alert_rules)


def add_job(
    name: str, job_type: str, cron: str, timezone: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    job = {
        "name": name,
        "job_type": job_type,
        "cron": cron,
        "timezone": timezone,
        "payload": payload or {},
        "enabled": True,
    }
    _job_defs.append(job)
    sched = get_scheduler()
    trigger = CronTrigger.from_crontab(cron, timezone=timezone)

    async def _runner() -> None:
        if job_type == "dca":
            await run_dca_job(payload or {})
        elif job_type == "analysis":
            await scheduled_analysis_stub(payload or {})
        else:
            await scan_alerts()

    sched.add_job(_runner, trigger=trigger, id=name, replace_existing=True)
    return job


def list_jobs() -> list[dict[str, Any]]:
    return list(_job_defs)


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        # default alert scan every 5 minutes
        sched.add_job(scan_alerts, "interval", minutes=5, id="alert_scan", replace_existing=True)
        sched.start()
        log.info("scheduler_started")


def shutdown_scheduler() -> None:
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
