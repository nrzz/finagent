# LLM setup

FinAgent uses LiteLLM. Configure via the Setup Wizard or Settings UI.

| Provider | Base URL | Notes |
|----------|----------|-------|
| ollama | `http://localhost:11434` | Best for privacy; 3B models use JSON tool fallback |
| openai | (default) | Needs `OPENAI_API_KEY` |
| anthropic | (default) | Needs `ANTHROPIC_API_KEY` |
| openrouter | (default) | Needs `OPENROUTER_API_KEY` |
| groq | (default) | Fast cloud inference |
| openai-compatible | your URL | LM Studio, vLLM, etc. |

Store keys in Settings → Secrets (encrypted) or `.env`.
