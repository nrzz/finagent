"""Agent tools — validated args, no settings/live-mode mutation."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from finagent.data import get_market_registry
from finagent.trading import get_paper_broker

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


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


TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_quote",
            "description": "Get latest quote with source and timestamp",
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
            "description": "Get option chain for an underlying",
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
            "description": "Get paper portfolio positions and cash",
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
                    "confirmed": {
                        "type": "boolean",
                        "description": "Must stay false unless the user already confirmed in the UI",
                    },
                },
                "required": ["symbol", "side", "quantity", "price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_screener",
            "description": "Run a simple symbol screener",
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
            "description": "Search symbols across enabled markets",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]


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
    # best-effort marks
    for sym in list(broker.account.positions.keys()):
        try:
            q = await get_market_registry().get_quote(sym)
            marks[sym] = q.price
        except Exception:
            continue
    return {
        "cash": str(broker.account.cash),
        "currency": broker.account.currency,
        "realized_pnl": str(broker.account.realized_pnl),
        "equity": str(broker.equity(marks)),
        "positions": broker.positions_snapshot(marks),
        "source": "paper_broker",
    }


async def _place_paper_order(args: dict[str, Any]) -> dict[str, Any]:
    parsed = PlacePaperOrderArgs.model_validate(args)
    confirmed = bool(args.get("confirmed", False))
    draft = {
        "symbol": parsed.symbol,
        "side": parsed.side.lower(),
        "quantity": parsed.quantity,
        "price": parsed.price,
        "asset_class": parsed.asset_class,
        "idempotency_key": parsed.idempotency_key,
        "order_type": "market",
    }
    if not confirmed:
        return {
            "pending_confirmation": True,
            "draft": draft,
            "mode": "paper",
            "warning": (
                "Paper trade only — not financial advice. Markets involve risk of loss. "
                "Confirm in the chat UI to execute on the paper account."
            ),
        }
    order = get_paper_broker().place_order(
        symbol=parsed.symbol,
        side=parsed.side,
        quantity=parsed.quantity,
        price=parsed.price,
        asset_class=parsed.asset_class,
        idempotency_key=parsed.idempotency_key,
        force_open_market=True,  # agent paper orders allowed off-hours for usability
    )
    return order.to_dict()


async def _run_screener(args: dict[str, Any]) -> dict[str, Any]:
    parsed = ScreenerArgs.model_validate(args)
    universes = {
        "india_bluechips": ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"],
        "crypto_majors": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "watchlist": ["AAPL", "MSFT", "GOOGL", "RELIANCE.NS", "BTC/USDT"],
    }
    symbols = universes.get(parsed.universe, universes["watchlist"])
    rows = []
    for sym in symbols:
        try:
            q = await get_market_registry().get_quote(sym)
            rows.append(q.to_dict())
        except Exception as exc:
            rows.append({"symbol": sym, "error": str(exc)})
    return {
        "universe": parsed.universe,
        "quotes": rows,
        "as_of_note": "Each quote includes its own timestamp",
    }


async def _search(args: dict[str, Any]) -> dict[str, Any]:
    parsed = SearchArgs.model_validate(args)
    return {"results": await get_market_registry().search(parsed.query)}


HANDLERS: dict[str, ToolHandler] = {
    "get_quote": _get_quote,
    "get_option_chain": _get_option_chain,
    "get_portfolio": _get_portfolio,
    "place_paper_order": _place_paper_order,
    "run_screener": _run_screener,
    "search_symbols": _search,
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
