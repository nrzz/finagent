# ADR 0004 — PWA + Capacitor

## Status

Accepted

## Context

Users want phone access without maintaining a separate React Native codebase. iOS sideloading is constrained without an Apple developer account.

## Decision

One React app → installable PWA (all platforms) + Capacitor Android APK for sideload/releases. Tauri desktop later.

## Consequences

+ Single UI codebase
+ APK for Android self-hosters
− iOS relies on PWA until someone maintains App Store packaging
