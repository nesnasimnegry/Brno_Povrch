---
name: safe-index-edit
description: Bezpečná úprava public/index.html (105 KB, jeden soubor, vanilla JS, hash routing). Použij při JAKÉKOLI editaci index.html — přidání komponenty, feature, oprava JS, změna routingu. Drží ověřovací rituál: cílené malé edity, esc() na user textu, po úpravě kontrola </html> a vyváženosti závorek ve <script>. Chrání produkci před rozbitým souborem.
---

# Bezpečná úprava index.html

`public/index.html` je celá appka v jednom souboru (~105 KB): vanilla JS, hash routing `#/...`, žádný build. Jedna rozbitá závorka = bílá stránka na produkci. Proto rituál.

## Před editací
- **Nikdy nepřepisuj celý soubor.** Cílené `Edit` s unikátním kontextem okolo.
- Najdi si přesné místo (Grep/Read s offsetem), needituj naslepo.
- Data model: `EVENTS` (ID prefix `a`=auto povrch, `u`=auto underground, `i`=ruční), `V`/`VENUES`, `VIMG` (kluby s fotkou), `COORDS` (mapa), `MODE`. Grabbery přepisují jen `a`/`u` bloky — ručních `i`, fotek ani SEO se nedotýkej.

## Pravidla kódu
- **Veškerý user/scrapnutý text přes `esc()`** — XSS i rozbití HTML. Bez výjimky.
- Barvy přes `var(--primary)`, `var(--fg)`, `var(--accent)` — nikdy hardcode (viz [[brno-styl]]). Mód = třída na `<body>` (`mode-underground`/`mode-public`).
- Nové těžší závislosti (mapy, knihovny) lazy-load, ne render-blocking v `<head>` — vzor `ensureLeaflet()` (inject `<script>`/`<link>` až při potřebě).

## Ověření PO každé editaci (povinné)
1. Soubor končí `</html>`.
2. Ve hlavním `<script>` sedí složené závorky `{}`. Rychlý check v Pythonu: vytáhni nejdelší `<script>` blok a spočítej `{` vs `}` mimo stringy — musí být 0.
   - Naivní čítač `(`/`[` může hlásit zbytek kvůli regex literálům (`/^#\//`). Proto **porovnej s `git show HEAD:public/index.html`**: důležité je, že `{}` = 0 a bilance se oproti HEAD nezhoršila.
3. Když to jde, ověř v prohlížeči: `preview_start {name:"brno"}` → localhost:8765, `read_console_messages` bez chyb, dotčená routa reálně funguje.

## Po ověření
Deploy na produkci řeší [[deploy-verify]].
