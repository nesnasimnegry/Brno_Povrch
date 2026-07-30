---
name: web-perf-audit
description: Lighthouse-style audit výkonu a kvality snabba.pages.dev. Použij při „audit výkonu/rychlosti", „proč je to pomalé", před cílem Lighthouse 100, nebo po velké změně webu. Manuální průchod head/meta/render-blocking/konzole/DOM/obrázky → seřazené nálezy dle dopad/riziko.
---

# Audit výkonu webu

Browser MCP nemá vestavěný Lighthouse — číselné skóre dá **PageSpeed Insights** (pagespeed.web.dev, keyless API má denní kvótu) nebo lokální Chrome (F12 → Lighthouse). Tenhle skill je manuální audit vedoucí ke konkrétním fixům.

## Co projít
1. **`<head>` render-blocking** (největší výhra) — synchronní `<script>` bez `defer`/`async`, blokující CSS. Third-party knihovny (mapy) lazy-load jen když jsou potřeba (vzor `ensureLeaflet()` — inject až při otevření routy). Google Fonts async: `media="print" onload="this.media='all'"` + `<noscript>` fallback.
2. **SEO/meta** — `<html lang>`, title, description, canonical, OG+Twitter, JSON-LD (Organization+WebSite).
3. **Konzole** — `read_console_messages` bez chyb.
4. **Obrázky** — `loading="lazy"`, rozměry, hotlinky (Unsplash) vs. self-host.
5. **Síť** — `read_network_requests`: váha stránky, zbytečné third-party origins.

## Ověření fixu v prohlížeči
`preview_start {name:"brno"}` → localhost:8765. `javascript_tool` na computed hodnoty (např. `!!window.L` = knihovna se nenačetla na home), pak otevři dotčenou routu (`location.hash="#/mapa"`) a potvrď funkčnost + `read_console_messages` bez chyb.

## Stav (k 30.7.2026)
Hotovo & živě: Leaflet lazy-load + async fonty (commit 6612ea6). Zbývá: vlastní OG karta (→ [[og-karta]]), self-host Unsplash fotek (hero + pozadí klubů tahá 6× z Unsplash), přístupnost (→ [[a11y-audit]]). Fix editace → [[safe-index-edit]], nasazení → [[deploy-verify]].
