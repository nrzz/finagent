"""Agent tools — validated args, no settings/live-mode mutation."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from finagent.data import get_market_registry
from finagent.trading import get_paper_broker

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "ciphertext",
    "api_key",
    "api_secret",
    "hmac",
)


def _sanitize_public(data: dict[str, Any]) -> dict[str, Any]:
    """Drop secret-like keys; never return credentials to the agent."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        lk = str(k).lower()
        if lk == "secret_names" or any(s in lk for s in _SENSITIVE_KEY_FRAGMENTS):
            continue
        if isinstance(v, dict):
            out[k] = _sanitize_public(v)
        else:
            out[k] = v
    return out


class GetQuoteArgs(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)


class GetOptionChainArgs(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)


class PlacePaperOrderArgs(BaseModel):
    symbol: str
    side: str
    quantity: str
    price: str
    asset_class: str = "equity"
    idempotency_key: str | None = None


class ScreenerArgs(BaseModel):
    universe: str = Field(
        default="watchlist", description="watchlist|india_bluechips|crypto_majors"
    )


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=64)


class BrokerHealthArgs(BaseModel):
    broker: str | None = Field(default=None, max_length=32)


class WatchlistSymbolArgs(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    name: str | None = None
    asset_class: str = "equity"


class RemoveWatchlistArgs(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)


TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_quote",
            "description": "Read-only: get latest quote with source and timestamp",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_option_chain",
            "description": "Read-only: get option chain for an underlying",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": (
                "Read-only: paper portfolio positions/cash plus manual holdings. "
                "Does not place orders or change live mode."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_paper_order",
            "description": (
                "Propose or place a PAPER trade only (never live). "
                "Without confirmed=true the UI shows Confirm/Cancel. "
                "Do not set confirmed=true yourself — the user must confirm in the chat UI."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "string"},
                    "price": {"type": "string"},
                    "asset_class": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                },
                "required": ["symbol", "side", "quantity", "price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_screener",
            "description": "Read-only: run a simple symbol screener over a universe",
            "parameters": {
                "type": "object",
                "properties": {
                    "universe": {
                        "type": "string",
                        "enum": ["watchlist", "india_bluechips", "crypto_majors"],
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_symbols",
            "description": "Read-only: search symbols across enabled markets",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_alert",
            "description": "Create a price alert (above/below threshold). Does not trade or change live mode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "condition": {"type": "string", "enum": ["above", "below"]},
                    "threshold": {"type": "string"},
                },
                "required": ["symbol", "condition", "threshold"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "broker_health",
            "description": (
                "Read-only: healthcheck one broker (by name) or all registered adapters. "
                "Never returns secrets or credentials."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "broker": {
                        "type": "string",
                        "description": "Optional adapter name (paper, zerodha, angel, alpaca). Omit for all.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_watchlist",
            "description": "Read-only: list symbols on the watchlist",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_watchlist_symbol",
            "description": "Add a symbol to the watchlist (does not trade or change live mode)",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "name": {"type": "string"},
                    "asset_class": {"type": "string"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_watchlist_symbol",
            "description": "Remove a symbol from the watchlist (does not trade or change live mode)",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_alerts",
            "description": "Read-only: list price alert rules",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_jobs",
            "description": "Read-only: list scheduled automation jobs",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_last_error",
            "description": (
                "Read-only: summarize the most recent audit-log error/failure/rejection "
                "(does not expose secrets)."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class CreateAlertArgs(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    condition: str
    threshold: str


async def _get_quote(args: dict[str, Any]) -> dict[str, Any]:
    parsed = GetQuoteArgs.model_validate(args)
    quote = await get_market_registry().get_quote(parsed.symbol)
    return quote.to_dict()


async def _get_option_chain(args: dict[str, Any]) -> dict[str, Any]:
    parsed = GetOptionChainArgs.model_validate(args)
    return await get_market_registry().get_option_chain(parsed.symbol)


async def _get_portfolio(_args: dict[str, Any]) -> dict[str, Any]:
    broker = get_paper_broker()
    marks: dict[str, Any] = {}
    for sym in list(broker.account.positions.keys()):
        try:
            q = await get_market_registry().get_quote(sym)
            marks[sym] = q.price
        except Exception:
            continue
    paper = {
        "cash": str(broker.account.cash),
        "currency": broker.account.currency,
        "realized_pnl": str(broker.account.realized_pnl),
        "equity": str(broker.equity(marks)),
        "positions": broker.positions_snapshot(marks),
    }
    manual: list[dict[str, Any]] = []
    try:
        from sqlalchemy import select

        from finagent.db import get_session_factory
        from finagent.db.models import Holding

        async with get_session_factory()() as session:
            rows = (await session.execute(select(Holding))).scalars().all()
            for r in rows:
                manual.append(
                    {
                        "symbol": r.symbol,
                        "quantity": r.quantity,
                        "avg_cost": r.avg_cost,
                        "account": r.account,
                        "notes": r.notes,
                    }
                )
    except Exception as exc:
        manual = [{"error": str(exc)}]
    return {
        "paper": paper,
        "manual_holdings": manual,
        "source": "paper_broker+holdings",
        "note": "Not financial advice. Paper and manual books are separate until you sync a broker.",
    }


async def _run_screener(args: dict[str, Any]) -> dict[str, Any]:
    parsed = ScreenerArgs.model_validate(args)
    universes = {
        "india_bluechips": ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"],
        "crypto_majors": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "watchlist": ["AAPL", "MSFT", "GOOGL", "RELIANCE.NS", "BTC/USDT"],
    }
    symbols = list(universes.get(parsed.universe, universes["watchlist"]))
    if parsed.universe == "watchlist":
        try:
            from sqlalchemy import select

            from finagent.db import get_session_factory
            from finagent.db.models import WatchlistItem

            async with get_session_factory()() as session:
                rows = (await session.execute(select(WatchlistItem))).scalars().all()
                if rows:
                    symbols = [r.symbol for r in rows]
        except Exception:
            pass
    rows = []
    for sym in symbols:
        try:
            q = await get_market_registry().get_quote(sym)
            rows.append(q.to_dict())
        except Exception as exc:
            rows.append({"symbol": sym, "error": str(exc)})

    # Sort by change_pct when present (honest % movers within universe)
    def _chg(r: dict[str, Any]) -> float:
        try:
            return float(r.get("change_pct") or 0)
        except Exception:
            return 0.0

    rows_sorted = sorted(rows, key=_chg, reverse=True)
    return {
        "universe": parsed.universe,
        "quotes": rows_sorted,
        "as_of_note": "Each quote includes its own timestamp. Not exchange top-movers — your universe only.",
    }


async def _place_paper_order(args: dict[str, Any]) -> dict[str, Any]:
    parsed = PlacePaperOrderArgs.model_validate(args)
    # Never trust LLM/tool `confirmed` — only the trading API / UI may confirm fills.
    draft = {
        "symbol": parsed.symbol,
        "side": parsed.side.lower(),
        "quantity": parsed.quantity,
        "price": parsed.price,
        "asset_class": parsed.asset_class,
        "idempotency_key": parsed.idempotency_key,
        "order_type": "market",
    }
    return {
        "pending_confirmation": True,
        "draft": draft,
        "mode": "paper",
        "warning": (
            "Paper trade only — not financial advice. Markets involve risk of loss. "
            "Confirm in the chat UI to execute on the paper account."
        ),
    }


async def _search(args: dict[str, Any]) -> dict[str, Any]:
    parsed = SearchArgs.model_validate(args)
    return {"results": await get_market_registry().search(parsed.query)}


async def _create_alert(args: dict[str, Any]) -> dict[str, Any]:
    parsed = CreateAlertArgs.model_validate(args)
    cond = parsed.condition.lower()
    if cond not in ("above", "below"):
        raise ValueError("condition must be above or below")
    from finagent.scheduler import add_alert

    return await add_alert(parsed.symbol.upper(), cond, parsed.threshold)


async def _broker_health(args: dict[str, Any]) -> dict[str, Any]:
    parsed = BrokerHealthArgs.model_validate(args)
    from finagent.brokers import get_broker_registry

    registry = get_broker_registry()
    adapters = registry.list_adapters()
    if parsed.broker:
        name = parsed.broker.strip().lower()
        adapters = [a for a in adapters if a.get("name") == name]
        if not adapters:
            raise ValueError(f"Unknown broker: {parsed.broker}")

    results: list[dict[str, Any]] = []
    for meta in adapters:
        name = str(meta.get("name") or "")
        try:
            adapter = registry.get(name)
            hc = await adapter.healthcheck()
        except Exception as exc:
            hc = {"ok": False, "name": name, "status": f"error:{exc}", "error": str(exc)}
        safe_meta = {
            k: meta[k]
            for k in ("name", "display_name", "supports_live", "configured", "session")
            if k in meta
        }
        merged = {**safe_meta, **(hc if isinstance(hc, dict) else {"raw": hc})}
        results.append(_sanitize_public(merged))
    return {
        "brokers": results,
        "note": "Read-only healthcheck. Secrets and credentials are never included.",
    }


async def _list_watchlist(_args: dict[str, Any]) -> dict[str, Any]:
    from sqlalchemy import select

    from finagent.db import get_session_factory
    from finagent.db.models import WatchlistItem

    async with get_session_factory()() as session:
        rows = (await session.execute(select(WatchlistItem))).scalars().all()
        return {
            "items": [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "name": r.name,
                    "asset_class": r.asset_class,
                }
                for r in rows
            ]
        }


async def _add_watchlist_symbol(args: dict[str, Any]) -> dict[str, Any]:
    parsed = WatchlistSymbolArgs.model_validate(args)
    from sqlalchemy import select

    from finagent.db import get_session_factory
    from finagent.db.models import WatchlistItem

    symbol = parsed.symbol.upper().strip()
    async with get_session_factory()() as session:
        existing = (
            await session.execute(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
        ).scalar_one_or_none()
        if existing:
            return {"ok": True, "symbol": existing.symbol, "already_present": True}
        item = WatchlistItem(symbol=symbol, name=parsed.name, asset_class=parsed.asset_class)
        session.add(item)
        await session.commit()
        return {"ok": True, "symbol": item.symbol, "already_present": False}


async def _remove_watchlist_symbol(args: dict[str, Any]) -> dict[str, Any]:
    parsed = RemoveWatchlistArgs.model_validate(args)
    from sqlalchemy import select

    from finagent.db import get_session_factory
    from finagent.db.models import WatchlistItem

    symbol = parsed.symbol.upper().strip()
    async with get_session_factory()() as session:
        row = (
            await session.execute(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
        ).scalar_one_or_none()
        if row:
            await session.delete(row)
            await session.commit()
            return {"ok": True, "symbol": symbol, "removed": True}
        return {"ok": True, "symbol": symbol, "removed": False}


async def _list_alerts(_args: dict[str, Any]) -> dict[str, Any]:
    from finagent.scheduler import list_alerts

    return {"alerts": await list_alerts()}


async def _list_jobs(_args: dict[str, Any]) -> dict[str, Any]:
    from finagent.scheduler import list_jobs

    return {"jobs": await list_jobs()}


def _detail_has_error(detail: Any) -> bool:
    if not isinstance(detail, dict):
        return False
    if detail.get("error"):
        return True
    return detail.get("ok") is False


async def _explain_last_error(_args: dict[str, Any]) -> dict[str, Any]:
    from sqlalchemy import select

    from finagent.db import get_session_factory
    from finagent.db.models import AuditLog

    async with get_session_factory()() as session:
        rows = (
            (await session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(40)))
            .scalars()
            .all()
        )

    matches: list[dict[str, Any]] = []
    for r in rows:
        action = r.action or ""
        action_l = action.lower()
        detail = r.detail if isinstance(r.detail, dict) else {}
        action_hit = any(x in action_l for x in ("error", "fail", "reject"))
        detail_hit = _detail_has_error(detail)
        if not (action_hit or detail_hit):
            continue
        safe_detail = _sanitize_public(detail) if detail else {}
        err = safe_detail.get("error") or safe_detail.get("detail") or action
        matches.append(
            {
                "id": r.id,
                "actor": r.actor,
                "action": action,
                "error": err if isinstance(err, str) else str(err),
                "detail": safe_detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )

    if not matches:
        return {
            "found": False,
            "summary": "No recent error/fail/reject entries in the audit log.",
            "recent": [],
        }

    last = matches[0]
    summary = (
        f"Last issue: action={last['action']} "
        f"at {last.get('created_at') or 'unknown'} — {last.get('error')}"
    )
    return {
        "found": True,
        "summary": summary,
        "last": last,
        "recent": matches[:5],
        "note": "Read-only audit summary. Secrets are redacted.",
    }


HANDLERS: dict[str, ToolHandler] = {
    "get_quote": _get_quote,
    "get_option_chain": _get_option_chain,
    "get_portfolio": _get_portfolio,
    "place_paper_order": _place_paper_order,
    "run_screener": _run_screener,
    "search_symbols": _search,
    "create_alert": _create_alert,
    "broker_health": _broker_health,
    "list_watchlist": _list_watchlist,
    "add_watchlist_symbol": _add_watchlist_symbol,
    "remove_watchlist_symbol": _remove_watchlist_symbol,
    "list_alerts": _list_alerts,
    "list_jobs": _list_jobs,
    "explain_last_error": _explain_last_error,
}


async def execute_tool(name: str, arguments: dict[str, Any] | str) -> dict[str, Any]:
    if name not in HANDLERS:
        return {"error": f"Unknown tool: {name}"}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return {"error": "Invalid tool arguments JSON"}
    try:
        result = await HANDLERS[name](arguments)
        return {"ok": True, "tool": name, "result": result}
    except Exception as exc:
        return {"ok": False, "tool": name, "error": str(exc)}
