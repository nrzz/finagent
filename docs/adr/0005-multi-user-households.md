# ADR 0005 — Multi-user households

## Status

Proposed (foundations only — no schema migration in 0.2.x)

## Context

FinAgent is single-operator today: one local install, one primary user. Households and shared paper books are on the roadmap, but shipping a roles migration early risks breaking existing SQLite installs for little gain.

## Current model

`User` already has `is_admin: bool` (default `True`). The first registered user is admin; auth payloads expose `is_admin`. There is **no** `role` enum yet — treat `is_admin` as the interim privilege flag.

Do **not** add a `User.role` column until a household model exists and an Alembic revision is intentional.

## Future roles (target)

| Role | Intent |
|------|--------|
| **owner** | Household admin: invite/remove members, manage live broker secrets, Panic Stop, settings |
| **member** | Shared paper book + read portfolio/chat; no live credentials or kill-switch changes |

## Paper vs live (target policy)

- **Paper:** may be **shared** within a household (one practice book, shared blotter).
- **Live:** remains **private** to the owner (or explicitly delegated later) — API keys and confirmations never shared by default.

## Decision

1. Document multi-user here; keep single-user runtime.
2. Reuse `is_admin` until households land; map owner ≈ `is_admin=True`, member ≈ `is_admin=False` when introduced.
3. Prefer ADR + PROJECT.md backlog over risky schema migration in 0.2.x.

## Consequences

+ Clear product intent without migration churn  
+ Existing installs stay compatible  
− UI/API still single-tenant until a later sprint implements households  
