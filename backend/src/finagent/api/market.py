"""Market, portfolio, trading, automation APIs."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finagent.api.auth import get_current_user
from finagent.brokers import BrokerOrderRequest, get_broker_registry
from finagent.data import get_market_registry
from finagent.db import get_db
from finagent.db.models import AuditLog, Cashflow, Holding, Notification, User, WatchlistItem
from finagent.portfolio import allocation_weights
from finagent.portfolio.money import D
from finagent.portfolio.pnl import Lot, apply_split, avg_cost, xirr
from finagent.scheduler import add_alert, add_job, list_alerts, list_jobs
from finagent.trading import black_scholes_greeks, estimate_margin, get_paper_broker, lot_size
from finagent.trading.persist import save_paper_to_db

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/market/quote/{symbol:path}")
async def quote(symbol: str, user: User = Depends(get_current_user)) -> dict[str, Any]:
    try:
        q = await get_market_registry().get_quote(symbol)
        return q.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/market/search")
async def search(q: str, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"results": await get_market_registry().search(q)}


@router.get("/market/history/{symbol:path}")
async def history(
    symbol: str, period: str = "1mo", user: User = Depends(get_current_user)
) -> dict[str, Any]:
    rows = await get_market_registry().get_history(symbol, period)
    return {"symbol": symbol, "period": period, "candles": rows}


@router.get("/market/options/{symbol:path}")
async def options(symbol: str, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return await get_market_registry().get_option_chain(symbol)


@router.get("/watchlist")
async def get_watchlist(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    rows = (await db.execute(select(WatchlistItem))).scalars().all()
    return {
        "items": [
            {"id": r.id, "symbol": r.symbol, "name": r.name, "asset_class": r.asset_class}
            for r in rows
        ]
    }


class WatchlistAdd(BaseModel):
    symbol: str
    name: str | None = None
    asset_class: str = "equity"


@router.post("/watchlist")
async def add_watchlist(
    body: WatchlistAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    item = WatchlistItem(symbol=body.symbol.upper(), name=body.name, asset_class=body.asset_class)
    db.add(item)
    await db.commit()
    return {"ok": True, "symbol": item.symbol}


@router.delete("/watchlist/{symbol}")
async def del_watchlist(
    symbol: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    result = await db.execute(select(WatchlistItem).where(WatchlistItem.symbol == symbol.upper()))
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
    return {"ok": True}


class HoldingIn(BaseModel):
    symbol: str
    quantity: str
    avg_cost: str
    currency: str = "INR"
    asset_class: str = "equity"
    account: str = "default"
    notes: str | None = None


@router.get("/portfolio")
async def portfolio(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    rows = (await db.execute(select(Holding))).scalars().all()
    paper = get_paper_broker()
    marks: dict[str, Any] = {}
    holdings_out = []
    values: dict[str, Any] = {}
    for r in rows:
        try:
            q = await get_market_registry().get_quote(r.symbol)
            mark = q.price
            marks[r.symbol] = mark
            mv = D(r.quantity) * mark
            values[r.symbol] = mv
            holdings_out.append(
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "quantity": r.quantity,
                    "avg_cost": r.avg_cost,
                    "currency": r.currency,
                    "asset_class": r.asset_class,
                    "mark": str(mark),
                    "market_value": str(mv),
                    "unrealized_pnl": str((mark - D(r.avg_cost)) * D(r.quantity)),
                    "source": q.source,
                    "as_of": q.as_of.isoformat(),
                    "stale": q.stale,
                }
            )
        except Exception as exc:
            holdings_out.append(
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "quantity": r.quantity,
                    "avg_cost": r.avg_cost,
                    "error": str(exc),
                }
            )
    paper_positions = paper.positions_snapshot(
        {k: D(v) if not isinstance(v, type(D(0))) else v for k, v in marks.items()}
    )
    weights = allocation_weights({k: D(v) for k, v in values.items()}) if values else {}
    return {
        "holdings": holdings_out,
        "paper": {
            "cash": str(paper.account.cash),
            "currency": paper.account.currency,
            "positions": paper_positions,
            "realized_pnl": str(paper.account.realized_pnl),
            "equity": str(paper.equity(marks)),
        },
        "allocation_pct": {k: str(v) for k, v in weights.items()},
        "disclaimer": "Not financial advice. Data may be delayed.",
    }


@router.post("/portfolio/holdings")
async def add_holding(
    body: HoldingIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        qty = str(D(body.quantity))
        cost = str(D(body.avg_cost))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    h = Holding(
        symbol=body.symbol.upper(),
        quantity=qty,
        avg_cost=cost,
        currency=body.currency,
        asset_class=body.asset_class,
        account=body.account,
        notes=body.notes,
    )
    db.add(h)
    db.add(AuditLog(actor=user.username, action="holding_add", detail={"symbol": h.symbol}))
    await db.commit()
    return {"ok": True, "id": h.id}


@router.post("/portfolio/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    count = 0
    skipped: list[str] = []
    for row in reader:
        symbol = (row.get("symbol") or row.get("Symbol") or "").strip()
        if not symbol:
            continue
        qty = row.get("quantity") or row.get("Quantity") or "0"
        cost = row.get("avg_cost") or row.get("AvgCost") or row.get("price") or "0"
        currency = row.get("currency") or row.get("Currency") or "INR"
        asset_class = row.get("asset_class") or row.get("AssetClass") or "equity"
        try:
            db.add(
                Holding(
                    symbol=symbol.upper(),
                    quantity=str(D(qty)),
                    avg_cost=str(D(cost)),
                    currency=currency,
                    asset_class=asset_class,
                )
            )
            count += 1
        except ValueError as exc:
            skipped.append(f"{symbol}: {exc}")
    db.add(
        AuditLog(
            actor=user.username,
            action="csv_import",
            detail={"count": count, "skipped": skipped},
        )
    )
    await db.commit()
    return {"ok": True, "imported": count, "skipped": skipped}


class OrderIn(BaseModel):
    symbol: str
    side: str
    quantity: str
    price: str
    order_type: str = "market"
    asset_class: str = "equity"
    idempotency_key: str | None = None
    confirmed: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


@router.get("/trading/blotter")
async def blotter(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"orders": get_paper_broker().blotter()}


@router.post("/trading/order")
async def place_order(
    body: OrderIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    meta = {"mark_price": body.price, **(body.meta or {})}
    req = BrokerOrderRequest(
        symbol=body.symbol,
        side=body.side,
        quantity=body.quantity,
        order_type=body.order_type,
        limit_price=body.price if body.order_type == "limit" else None,
        idempotency_key=body.idempotency_key,
        asset_class=body.asset_class,
        meta=meta,
    )
    result = await get_broker_registry().place_order_safe(req, confirmed=body.confirmed)
    await save_paper_to_db(db)
    db.add(AuditLog(actor=user.username, action="place_order", detail=result))
    await db.commit()
    return result


@router.get("/trading/brokers")
async def brokers(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"brokers": get_broker_registry().list_adapters()}


@router.post("/trading/paper/reset")
async def reset_paper(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    get_paper_broker().reset()
    await save_paper_to_db(db)
    db.add(AuditLog(actor=user.username, action="paper_reset", detail={}))
    await db.commit()
    return {"ok": True}


class GreeksIn(BaseModel):
    spot: float
    strike: float
    t_years: float
    rate: float = 0.07
    iv: float = 0.2
    option_type: str = "CE"
    underlying: str = "NIFTY"
    premium: float | None = None
    quantity_lots: int = 1


@router.post("/trading/fno/greeks")
async def greeks(body: GreeksIn, user: User = Depends(get_current_user)) -> dict[str, Any]:
    g = black_scholes_greeks(
        body.spot, body.strike, body.t_years, body.rate, body.iv, body.option_type
    )
    lot = lot_size(body.underlying)
    prem = D(body.premium) if body.premium is not None else D(body.spot * 0.01)
    return {
        "delta": g.delta,
        "gamma": g.gamma,
        "theta": g.theta,
        "vega": g.vega,
        "iv": g.iv,
        "lot_size": lot,
        "margin_estimate": str(estimate_margin(prem, lot, body.quantity_lots)),
        "disclaimer": "Illustrative margin only — not exchange SPAN. Paper trading.",
    }


class OptionOrderIn(BaseModel):
    underlying: str
    expiry: str  # YYYY-MM-DD
    strike: str
    option_type: str = Field(pattern="^(CE|PE)$")
    side: str = "buy"
    quantity_lots: int = Field(ge=1, le=100)
    premium: str
    confirmed: bool = False


@router.post("/trading/fno/order")
async def place_option_order(
    body: OptionOrderIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    lot = lot_size(body.underlying)
    qty = D(lot) * D(body.quantity_lots)
    symbol = f"{body.underlying.upper()}|{body.expiry}|{body.strike}|{body.option_type}"
    req = BrokerOrderRequest(
        symbol=symbol,
        side=body.side,
        quantity=str(qty),
        order_type="market",
        limit_price=None,
        asset_class="option",
        meta={
            "mark_price": body.premium,
            "underlying": body.underlying.upper(),
            "expiry": body.expiry,
            "strike": body.strike,
            "option_type": body.option_type,
            "lot_size": lot,
            "quantity_lots": body.quantity_lots,
            "margin_estimate": str(
                estimate_margin(D(body.premium), lot, body.quantity_lots)
            ),
        },
    )
    result = await get_broker_registry().place_order_safe(req, confirmed=body.confirmed)
    await save_paper_to_db(db)
    db.add(AuditLog(actor=user.username, action="fno_paper_order", detail=result))
    await db.commit()
    return result


class AlertIn(BaseModel):
    symbol: str
    condition: str = Field(pattern="^(above|below)$")
    threshold: str


@router.get("/automation/alerts")
async def alerts(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"alerts": await list_alerts()}


@router.post("/automation/alerts")
async def create_alert(body: AlertIn, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return await add_alert(body.symbol, body.condition, body.threshold)


class JobIn(BaseModel):
    name: str
    job_type: str
    cron: str = "0 9 * * 1-5"
    timezone: str = "Asia/Kolkata"
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/automation/jobs")
async def jobs(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"jobs": await list_jobs()}


@router.post("/automation/jobs")
async def create_job(body: JobIn, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return await add_job(body.name, body.job_type, body.cron, body.timezone, body.payload)


@router.get("/notifications")
async def notifications(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    rows = (
        await db.execute(select(Notification).order_by(Notification.id.desc()).limit(50))
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "kind": r.kind,
                "title": r.title,
                "body": r.body,
                "payload": r.payload,
                "read": r.read,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/notifications/{nid}/read")
async def mark_notification_read(
    nid: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    row = await db.get(Notification, nid)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    row.read = True
    await db.commit()
    return {"ok": True}


class CashflowIn(BaseModel):
    amount: str
    on_date: str  # YYYY-MM-DD
    note: str | None = None


@router.get("/portfolio/xirr")
async def portfolio_xirr(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    from datetime import date as date_cls

    rows = (await db.execute(select(Cashflow).order_by(Cashflow.on_date))).scalars().all()
    flows = [(date_cls.fromisoformat(r.on_date), D(r.amount)) for r in rows]
    # Append current paper equity as terminal positive cashflow for illustrative XIRR
    paper = get_paper_broker()
    if flows:
        flows.append((date_cls.today(), paper.account.cash))
    rate = xirr(flows) if len(flows) >= 2 else None
    return {
        "xirr_pct": str(rate) if rate is not None else None,
        "cashflows": [
            {"amount": r.amount, "on_date": r.on_date, "note": r.note, "id": r.id} for r in rows
        ],
        "note": "Not financial advice. XIRR needs invest (-) and redeem (+) cashflows.",
    }


@router.post("/portfolio/cashflows")
async def add_cashflow(
    body: CashflowIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = Cashflow(amount=str(D(body.amount)), on_date=body.on_date, note=body.note)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "amount": row.amount, "on_date": row.on_date, "note": row.note}


class CorpActionIn(BaseModel):
    symbol: str
    ratio_num: str = "2"
    ratio_den: str = "1"
    account: str = "default"


@router.post("/portfolio/corporate-action")
async def corporate_action(
    body: CorpActionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    sym = body.symbol.upper()
    rows = (
        await db.execute(select(Holding).where(Holding.symbol == sym, Holding.account == body.account))
    ).scalars().all()
    if not rows:
        # Also apply to paper book
        paper = get_paper_broker()
        lots = paper.account.positions.get(sym)
        if not lots:
            raise HTTPException(status_code=404, detail="Holding not found")
        paper.account.positions[sym] = apply_split(lots, D(body.ratio_num), D(body.ratio_den))
        await save_paper_to_db(db)
        db.add(
            AuditLog(
                actor=user.username,
                action="corporate_action_split",
                detail={"symbol": sym, "num": body.ratio_num, "den": body.ratio_den, "scope": "paper"},
            )
        )
        await db.commit()
        return {"ok": True, "scope": "paper", "symbol": sym}

    for h in rows:
        lots = [Lot(quantity=D(h.quantity), cost=D(h.avg_cost))]
        new_lots = apply_split(lots, D(body.ratio_num), D(body.ratio_den))
        h.quantity = str(sum((lot.quantity for lot in new_lots), D(0)))
        h.avg_cost = str(avg_cost(new_lots))
    db.add(
        AuditLog(
            actor=user.username,
            action="corporate_action_split",
            detail={"symbol": sym, "num": body.ratio_num, "den": body.ratio_den},
        )
    )
    await db.commit()
    return {"ok": True, "scope": "holdings", "symbol": sym}


@router.get("/portfolio/benchmark")
async def portfolio_benchmark(
    symbol: str = "^NSEI",
    period: str = "6mo",
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    candles = await get_market_registry().get_history(symbol, period)
    return {
        "symbol": symbol,
        "period": period,
        "candles": candles,
        "disclaimer": "Benchmark for comparison only. Not financial advice.",
    }


@router.get("/audit")
async def audit_log(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    rows = (
        (await db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(100))).scalars().all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "actor": r.actor,
                "action": r.action,
                "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
