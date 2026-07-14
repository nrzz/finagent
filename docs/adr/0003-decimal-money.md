# ADR 0003 — Decimal money math

## Status

Accepted

## Context

Binary floats silently corrupt P&L (classic finance bug).

## Decision

All prices, quantities, and P&L use `decimal.Decimal`, stored as strings in SQLite, with Hypothesis property tests on FIFO.

## Consequences

+ Correctness
− Slightly more verbose code
