"""Streaming chat API."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from finagent.agent import AgentLoop
from finagent.api.auth import get_current_user
from finagent.db import get_db
from finagent.db.models import AuditLog, ChatMessage, User

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[dict[str, Any]] = Field(default_factory=list)


@router.post("")
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    async def audit(action: str, detail: dict[str, Any]) -> None:
        db.add(AuditLog(actor=user.username, action=action, detail=detail))
        await db.commit()

    agent = AgentLoop(audit=audit)
    result = await agent.run(body.message, body.history)
    db.add(ChatMessage(role="user", content=body.message))
    db.add(
        ChatMessage(
            role="assistant",
            content=result.get("content") or "",
            tool_calls={"trace": result.get("tool_trace")},
            citations={"items": result.get("citations")},
        )
    )
    await db.commit()
    return result


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    async def audit(action: str, detail: dict[str, Any]) -> None:
        db.add(AuditLog(actor=user.username, action=action, detail=detail))
        await db.commit()

    agent = AgentLoop(audit=audit)

    async def event_gen():
        final_content = ""
        citations: list[Any] = []
        tool_trace: list[Any] = []
        async for event in agent.stream_events(body.message, body.history):
            if event.get("type") == "final":
                final_content = event.get("content") or ""
                citations = event.get("citations") or []
                tool_trace = event.get("tool_trace") or []
            yield f"data: {json.dumps(event)}\n\n"
        db.add(ChatMessage(role="user", content=body.message))
        db.add(
            ChatMessage(
                role="assistant",
                content=final_content,
                tool_calls={"trace": tool_trace},
                citations={"items": citations},
            )
        )
        await db.commit()
        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(event_gen(), media_type="text/event-stream")
