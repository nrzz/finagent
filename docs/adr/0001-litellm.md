# ADR 0001 — OpenAI-compatible LLM router (httpx)

## Status

Accepted

## Context

Users need Ollama, LM Studio, OpenAI, Anthropic, OpenRouter, Groq, and arbitrary OpenAI-compatible endpoints. Pulling LiteLLM added fragile native build deps on some platforms.

## Decision

Use a thin OpenAI-compatible httpx client as the completion router (Ollama, OpenAI, OpenRouter, Groq, LM Studio, Anthropic Messages API) with FinAgent-owned tool-mode selection (native vs JSON fallback). Avoids heavy framework lock-in.

## Consequences

+ One config surface
+ Easy to add providers
− Dependency size; pin and audit regularly
