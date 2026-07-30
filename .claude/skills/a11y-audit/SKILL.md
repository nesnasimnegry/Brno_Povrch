---
name: a11y-audit
description: Audit přístupnosti (a11y) snabba.pages.dev. Použij při „přístupnost", „a11y", cílu Lighthouse 100, nebo když někdo nemůže web ovládat klávesnicí/čtečkou. Kontrast v obou módech, focus stavy, ARIA, alt, sémantika — doplňuje web-perf-audit.
---

# Audit přístupnosti

Doplněk k [[web-perf-audit]] pro cíl „Lighthouse 100" (kategorie Accessibility).

## Co projít
1. **Kontrast v OBOU módech** — underground (žlutá `#ecc400` na `#0c0b0a`) i povrch (cyan `#37d4e6` na `#0c0b0a`). Text vůči pozadí ≥ 4.5:1 (velký text 3:1). Pozor na `--mut` šedou na kartách a mono labely.
2. **Focus stavy** — každý interaktivní prvek viditelný `:focus-visible`. Klávesnicová navigace (tab) projde celý web, včetně přepínače módu, jazyka, lupy, mapy.
3. **Sémantika** — `<button>` pro akce (ne klikací `<div>`), `<nav>`/`<main>`, nadpisy v pořadí. Hash routing nesmí ztratit focus — po přechodu routy dej focus na `<h1>` / `#app`.
4. **ARIA & alt** — ikonková tlačítka (lupa, sdílet, mód) mají `aria-label`. Obrázky smysluplný `alt`. Marquee a dekorativní prvky `aria-hidden="true"`.
5. **Reduced motion** — `@media(prefers-reduced-motion:reduce)` v CSS už je; nové animace musí spadat pod něj (viz [[brno-styl]]).

## Nástroje
Lokální Chrome F12 → Lighthouse (Accessibility) nebo axe DevTools. V browser MCP: `read_page` (accessibility tree ukáže chybějící labely/role), `javascript_tool` na computed kontrast.

## Fix
Editace → [[safe-index-edit]], barvy vždy přes `var(--...)`, ne hardcode. Nasazení → [[deploy-verify]].
