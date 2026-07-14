"""APScheduler jobs: alerts, analysis, DCA — persisted in DB."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from finagent.data import get_market_registry
from finagent.db import get_session_factory
from finagent.db.models import AlertRule, JobRun, Notification, ScheduledJob
from finagent.logging_setup import get_logger
from finagent.portfolio.money import D
from finagent.trading import get_paper_broker
from finagent.trading.fno import is_expired
from finagent.trading.persist import save_paper_to_db

log = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def _notify(kind: str, title: str, body: str, payload: dict[str, Any] | None = None) -> None:
    async with get_session_factory()() as session:
        session.add(
            Notification(kind=kind, title=title, body=body, payload=payload or {})
        )
        await session.commit()


async def scan_alerts() -> dict[str, Any]:
    triggered: list[dict[str, Any]] = []
    async with get_session_factory()() as session:
        rules = (await session.execute(select(AlertRule).where(AlertRule.active.is_(True)))).scalars().all()
        for rule in rules:
            try:
                q = await get_market_registry().get_quote(rule.symbol)
                thr = D(rule.threshold)
                cond = rule.condition
                hit = (cond == "above" and q.price >= thr) or (cond == "below" and q.price <= thr)
                if hit:
                    event = {
                        "symbol": rule.symbol,
                        "condition": cond,
                        "threshold": str(thr),
                        "price": str(q.price),
                        "as_of": q.as_of.isoformat(),
                        "source": q.source,
                    }
                    triggered.append(event)
                    rule.last_triggered_at = datetime.now(UTC)
                    session.add(
                        Notification(
                            kind="alert",
                            title=f"Alert: {rule.symbol} {cond} {thr}",
                            body=f"Price {q.price} ({q.source})",
                            payload=event,
                        )
                    )
                    log.info("alert_triggered", **event)
            except Exception as exc:
                log.warning("alert_scan_error", error=str(exc), symbol=rule.symbol)
        await session.commit()
        return {"triggered": triggered, "scanned": len(rules)}


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
    async with get_session_factory()() as session:
        await save_paper_to_db(session)
    return order.to_dict()


async def scheduled_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    """Fetch quotes and ask the agent for a short paper-mode summary."""
    symbols = payload.get("symbols") or ["RELIANCE.NS", "AAPL", "BTC/USDT"]
    quotes = []
    for s in symbols:
        try:
            q = await get_market_registry().get_quote(s)
            quotes.append(q.to_dict())
        except Exception as exc:
            quotes.append({"symbol": s, "error": str(exc)})
    summary = "Scheduled snapshot (not financial advice):\n"
    for q in quotes:
        if "error" in q:
            summary += f"- {q['symbol']}: error {q['error']}\n"
        else:
            summary += f"- {q.get('symbol')}: {q.get('price')} ({q.get('source')}) @ {q.get('as_of')}\n"
    try:
        from finagent.agent.loop import AgentLoop

        agent = AgentLoop()
        result = await agent.run(
            "Summarize these paper-mode quotes in 3 short bullets. Not financial advice.\n"
            + summary,
            history=[],
        )
        narrative = result.get("content") or summary
    except Exception as exc:
        narrative = summary + f"\n(Agent unavailable: {exc})"
    detail = {"type": "analysis", "quotes": quotes, "narrative": narrative}
    await _notify("job", "Scheduled analysis", narrative[:500], detail)
    return detail


async def square_off_expired_options() -> dict[str, Any]:
    """Close paper option positions whose expiry date has passed."""
    broker = get_paper_broker()
    closed: list[dict[str, Any]] = []
    today = date.today()
    for sym, lots in list(broker.account.positions.items()):
        # Option symbols stored like NIFTY|2024-01-25|22000|CE or meta on last order
        meta_expiry = None
        for order in broker.account.orders.values():
            if order.symbol == sym and order.meta.get("expiry"):
                meta_expiry = order.meta.get("expiry")
                break
        if not meta_expiry and "|" in sym:
            parts = sym.split("|")
            if len(parts) >= 2:
                meta_expiry = parts[1]
        if not meta_expiry:
            continue
        try:
            exp = date.fromisoformat(str(meta_expiry)[:10])
        except ValueError:
            continue
        if not is_expired(exp, today):
            continue
        qty = sum((lot.quantity for lot in lots), D(0))
        if qty <= 0:
            continue
        # Square off at last fill or avg cost
        mark = lots[0].cost if lots else D(0)
        for order in reversed(list(broker.account.orders.values())):
            if order.symbol == sym and order.avg_fill_price is not None:
                mark = order.avg_fill_price
                break
        result = broker.place_order(
            symbol=sym,
            side="sell",
            quantity=str(qty),
            price=str(mark),
            asset_class="option",
            force_open_market=True,
            meta={"job": "expiry_square_off", "expiry": str(exp)},
        )
        closed.append(result.to_dict())
    if closed:
        async with get_session_factory()() as session:
            await save_paper_to_db(session)
        await _notify(
            "job",
            "Expiry square-off",
            f"Closed {len(closed)} expired paper option position(s).",
            {"closed": closed},
        )
    return {"closed": closed}


async def add_alert(symbol: str, condition: str, threshold: str) -> dict[str, Any]:
    async with get_session_factory()() as session:
        rule = AlertRule(
            symbol=symbol.upper(),
            condition=condition,
            threshold=threshold,
            active=True,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return {
            "id": rule.id,
            "symbol": rule.symbol,
            "condition": rule.condition,
            "threshold": rule.threshold,
            "active": rule.active,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
        }


async def list_alerts() -> list[dict[str, Any]]:
    async with get_session_factory()() as session:
        rows = (await session.execute(select(AlertRule).order_by(AlertRule.id.desc()))).scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "condition": r.condition,
                "threshold": r.threshold,
                "active": r.active,
                "last_triggered_at": r.last_triggered_at.isoformat() if r.last_triggered_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


async def add_job(
    name: str, job_type: str, cron: str, timezone: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    async with get_session_factory()() as session:
        existing = (
            await session.execute(select(ScheduledJob).where(ScheduledJob.name == name))
        ).scalar_one_or_none()
        if existing:
            existing.job_type = job_type
            existing.cron = cron
            existing.timezone = timezone
            existing.payload = payload or {}
            existing.enabled = True
            job = existing
        else:
            job = ScheduledJob(
                name=name,
                job_type=job_type,
                cron=cron,
                timezone=timezone,
                payload=payload or {},
                enabled=True,
            )
            session.add(job)
        await session.commit()
        await session.refresh(job)
        _schedule_job_row(job)
        return {
            "id": job.id,
            "name": job.name,
            "job_type": job.job_type,
            "cron": job.cron,
            "timezone": job.timezone,
            "payload": job.payload,
            "enabled": job.enabled,
        }


async def list_jobs() -> list[dict[str, Any]]:
    async with get_session_factory()() as session:
        rows = (await session.execute(select(ScheduledJob))).scalars().all()
        out = []
        for j in rows:
            last = (
                await session.execute(
                    select(JobRun).where(JobRun.job_id == j.id).order_by(JobRun.id.desc()).limit(1)
                )
            ).scalar_one_or_none()
            out.append(
                {
                    "id": j.id,
                    "name": j.name,
                    "job_type": j.job_type,
                    "cron": j.cron,
                    "timezone": j.timezone,
                    "payload": j.payload,
                    "enabled": j.enabled,
                    "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
                    "last_run": {
                        "status": last.status,
                        "detail": last.detail,
                        "created_at": last.created_at.isoformat() if last and last.created_at else None,
                    }
                    if last
                    else None,
                }
            )
        return out


def _schedule_job_row(job: ScheduledJob) -> None:
    sched = get_scheduler()
    trigger = CronTrigger.from_crontab(job.cron, timezone=job.timezone)
    job_id = job.id
    job_type = job.job_type
    payload = dict(job.payload or {})
    name = job.name

    async def _runner() -> None:
        detail: dict[str, Any] = {}
        status = "ok"
        try:
            if job_type == "dca":
                detail = await run_dca_job(payload)
            elif job_type == "analysis":
                detail = await scheduled_analysis(payload)
            elif job_type == "square_off":
                detail = await square_off_expired_options()
            else:
                detail = await scan_alerts()
        except Exception as exc:
            status = "error"
            detail = {"error": str(exc)}
            log.warning("job_failed", name=name, error=str(exc))
        async with get_session_factory()() as session:
            row = await session.get(ScheduledJob, job_id)
            if row:
                row.last_run_at = datetime.now(UTC)
                session.add(JobRun(job_id=job_id, status=status, detail=detail))
                await session.commit()

    sched.add_job(_runner, trigger=trigger, id=name, replace_existing=True)


async def reload_jobs_from_db() -> None:
    async with get_session_factory()() as session:
        rows = (
            await session.execute(select(ScheduledJob).where(ScheduledJob.enabled.is_(True)))
        ).scalars().all()
        for job in rows:
            try:
                _schedule_job_row(job)
            except Exception as exc:
                log.warning("job_schedule_failed", name=job.name, error=str(exc))


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        sched.add_job(scan_alerts, "interval", minutes=5, id="alert_scan", replace_existing=True)
        sched.add_job(
            square_off_expired_options,
            "cron",
            hour=15,
            minute=35,
            timezone="Asia/Kolkata",
            id="fno_square_off",
            replace_existing=True,
        )
        sched.start()
        log.info("scheduler_started")


def shutdown_scheduler() -> None:
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)


# Sync wrappers used by older API paths — prefer async callers
def list_alerts_sync() -> list[dict[str, Any]]:
    import anyio

    return anyio.run(list_alerts)


def add_alert_sync(symbol: str, condition: str, threshold: str) -> dict[str, Any]:
    import anyio

    return anyio.run(add_alert, symbol, condition, threshold)
