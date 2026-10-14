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

## Which endpoints are allowed

For safety (SSRF), FinAgent only talks to `localhost` / `127.0.0.1` / `[::1]`, the known HTTPS cloud providers in the table above, and hosts the server operator lists in `FINAGENT_LLM_ALLOWED_HOSTS`. A local Ollama or LM Studio needs nothing extra.

For a model server on another machine, in Docker, or behind your own proxy, add its host to `.env` and restart:

```bash
FINAGENT_LLM_ALLOWED_HOSTS=192.168.1.50,ollama
```

Read the warning in [SECURITY.md](https://github.com/nrzz/finagent/blob/main/SECURITY.md) first: everyone who can log in to FinAgent can then make the server send requests to the listed hosts.
