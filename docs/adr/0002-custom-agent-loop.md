# ADR 0002 — Custom agent loop

## Status

Accepted

## Context

Heavy frameworks (LangChain et al.) add complexity and obscure control over tool permissions — dangerous for finance.

## Decision

Ship a small custom loop with Pydantic-validated tools, iteration caps, and an audit log. Tools cannot mutate settings or enable live trading.

## Consequences

+ Clear security boundary
+ Easy to reason about
− We maintain tool orchestration ourselves
