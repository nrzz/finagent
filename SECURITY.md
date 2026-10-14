# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

1. Use GitHub **Private vulnerability reporting** on this repository, or
2. Email the maintainers (replace with your contact when publishing).

Include:

- Description and impact
- Reproduction steps / PoC (non-destructive)
- Affected version / commit

We aim to acknowledge within 72 hours and ship a fix or mitigation ASAP.

## Scope notes

- FinAgent is self-hosted; you are responsible for network exposure (prefer Tailscale / reverse-proxy HTTPS).
- Live trading plugins can move real money — treat API keys as highly sensitive.
- The agent must never be able to enable live mode or read decrypted secrets; please report any bypass.
## Hardening notes (high-tier uplift)

- Secrets: Fernet ciphertext; KEK via Argon2id; secret upsert requires password re-auth
- Passwords: Argon2id (bcrypt migrates on next login); login rate-limited and audited
- Startup fails closed on insecure default JWT/Fernet secrets unless `FINAGENT_ALLOW_INSECURE_SECRETS=1`
- Wizard cannot enable live trading; live orders always need confirmation
- Kill switch **on** is instant (Panic Stop in header); turning kill switch **off** needs re-auth
- Live routing uses only `trading.default_broker` (never an accidental stub)
- LLM endpoint allow-list (SSRF): localhost and the known HTTPS cloud providers only, anything else needs `FINAGENT_LLM_ALLOWED_HOSTS` (see below); webhook/Discord/Slack URLs are SSRF-checked too (private IPs blocked unless `FINAGENT_ALLOW_PRIVATE_WEBHOOKS=1`)
- Agent cannot confirm paper fills without the trading UI / cannot enable live
- Structured logs redact passwords, tokens, and secrets
- Backups export ciphertext only � restore with the same `FINAGENT_SECRET_KEY`, then restart

## LLM endpoint allow-list (`FINAGENT_LLM_ALLOWED_HOSTS`)

The server sends your prompts, and the API key of the selected provider, to the LLM endpoint configured in Settings. So that a logged-in session (or a stolen token) cannot use that setting to make the server call arbitrary addresses, an endpoint is accepted only when it is

- `localhost`, a `127.x.x.x` address or `[::1]` - a local Ollama or LM Studio works with no setup;
- a known cloud API host over HTTPS: `api.openai.com`, `api.anthropic.com`, `openrouter.ai`, `api.groq.com`, `generativelanguage.googleapis.com`; or
- a host the **server operator** lists in `FINAGENT_LLM_ALLOWED_HOSTS` (environment variable or `.env`, comma separated, restart to apply).

Every URL must use `http://` or `https://` and must not contain `user:password@`, a query string or a fragment. Link-local (including cloud metadata), unspecified and multicast addresses are refused even when listed. Redirects are never followed.

```bash
# Ollama on another machine on your LAN, and the "ollama" service of docker-compose.yml
FINAGENT_LLM_ALLOWED_HOSTS=192.168.1.50,ollama
```

> **Warning:** every host you list can be reached, on any port, by anyone who can log in to FinAgent (the server will send requests there and show whether they worked). List only machines you trust, prefer exact IP addresses or names over broad ones, and use `https://` for anything that is not your own computer. The list can only be changed through the server environment, never from the UI or the API.

## Threat model (short)

| Risk | Mitigation |
|------|------------|
| Stolen laptop DB | Secrets encrypted; protect `.env` / `FINAGENT_SECRET_KEY` |
| Malicious LLM tool call | Agent cannot go live or set `confirmed`; tools cannot read secrets |
| SSRF via webhook | Host allowlist + block metadata/private IPs |
| SSRF via LLM endpoint | Endpoint allow-list (localhost, known cloud hosts, operator-listed hosts), no redirects, API keys only sent to those hosts |
| Accidental live order | Paper default; re-auth for live; confirm; Panic Stop |
