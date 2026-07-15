# Tauri desktop (plan)

Wrap the existing Vite UI + local FastAPI backend as a desktop app so users can replace always-on `START.bat` / console sessions with a single windowed process.

## Goals

- One native window hosting the React SPA (same build as web/PWA)
- Spawn or attach to the local backend on `127.0.0.1` (same as Docker/dev)
- Optional system tray + auto-start later; not required for v1

## Non-goals (this foundation)

- Full `cargo tauri init` scaffold (needs Rust toolchain on every contributor machine)
- Shipping signed installers in CI yet

## Suggested layout (when scaffolding)

```
frontend/
  src/           # existing Vite React app
  src-tauri/     # Tauri 2 project (created with `npm create tauri-app` or `tauri init`)
```

Placeholder: `frontend/src-tauri/.gitkeep` marks where the Rust project will live.

## Integration sketch

1. **Build UI** — `npm run build` → `frontend/dist`
2. **Tauri `devUrl` / `frontendDist`** — point at Vite in dev, `dist` in release
3. **Sidecar / beforeDevCommand** — start uvicorn (`python -m finagent` or existing entry) before the window opens; health-check `/api/health`
4. **CSP** — allow `connect-src http://127.0.0.1:*` for API + SSE chat
5. **Replace START.bat** — desktop shortcut launches Tauri; backend lifecycle tied to app exit (or tray keep-alive)

## Prerequisites

- Rust stable + platform build tools (MSVC on Windows)
- `@tauri-apps/cli` as a frontend optional dependency

## Status

Foundations landed in 0.2.x (this guide + placeholder). Full app remains a v0.3 roadmap item.
