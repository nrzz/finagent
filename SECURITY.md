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
- Live trading plugins can move real money â€” treat API keys as highly sensitive.
- The agent must never be able to enable live mode or read decrypted secrets; please report any bypass.
## Hardening notes (high-tier uplift)

- Secrets: Fernet ciphertext; KEK via Argon2id; secret upsert requires password re-auth
- Passwords: Argon2id (bcrypt migrates on next login); login rate-limited and audited
- Startup fails closed on insecure default JWT/Fernet secrets unless `FINAGENT_ALLOW_INSECURE_SECRETS=1`
- Wizard cannot enable live trading; live orders always need confirmation
- LLM URL SSRF allowlist; agent cannot confirm paper fills without the trading UI
- Backups export ciphertext only — restore with the same `FINAGENT_SECRET_KEY`, then restart
