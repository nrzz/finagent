# Remote access

Prefer **not** exposing port 8000 to the public internet.

## Tailscale / WireGuard (recommended)

Install Tailscale on the host and your phone/laptop. Reach FinAgent at `http://100.x.y.z:8000` over the mesh VPN.

## Reverse proxy + HTTPS

Example Caddy:

```
finagent.example.com {
  reverse_proxy 127.0.0.1:8000
}
```

Set `FINAGENT_CORS_ORIGINS` to your HTTPS origin if not using `*`.

## Mobile

- **PWA**: open the HTTPS URL in Chrome/Safari → Install / Add to Home Screen
- **APK**: download from GitHub Releases; on first launch enter your server URL (LAN IP or Tailscale IP)
