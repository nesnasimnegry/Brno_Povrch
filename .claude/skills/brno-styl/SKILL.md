---
name: brno-styl
description: Vizuální jazyk, animace a tón textů BRNO SCÉNY. Použij při psaní jakéhokoli UI textu (české i anglické copy, hlášky, prázdné stavy, e-maily, popisky), při přidávání komponent/tlačítek do public/index.html nebo klub-*.html, a při ladění barev, typografie či animací. Drží web konzistentní napříč módy UNDERGROUND/POVRCH.
---

# BRNO SCÉNA — styl

Publikum: **studenti a mladí v Brně**. Web je „průvodce scénou", ne korporát. Dva módy nejsou skin,
ale dvě nálady — text i vizuál se mění spolu s nimi.

## Duální mód (klíčové pravidlo)
| | UNDERGROUND | POVRCH |
|---|---|---|
| `--primary` | `#ecc400` (žlutá) | `#37d4e6` (cyan) |
| `--primary-fg` | tmavá na žluté | `#04222a` |
| `--accent` | `#c5362a` (rezavá) | `#ff5aa6` (růžová) |
| nálada | syrová, DIY, sklepní | velká, zářivá, mainstream |
| slovník | scéna, sklep, DIY, špunty, respekt k prostoru | koncerty, festivaly, lístky, diskotéky |

Barvy **nikdy nehardcoduj** — používej `var(--primary)`, `var(--fg)`, `var(--bg)`, `var(--accent)`.
Mód se přepíná třídou na `<body>`: `mode-underground` / `mode-public`.

## Tokeny
- `--bg:#0c0b0a` · `--fg:#efeae0` · `--mono:"JetBrains Mono",ui-monospace,monospace`
- Mono font = **labely, tlačítka, meta údaje, kickery**. Displejové písmo = nadpisy a běžný text.
- Nadpisy: `text-transform:uppercase`, těsný `line-height`, `clamp()` pro škálování.
- Malé labely: `font-size:12px`, `letter-spacing:.22em`, uppercase, barva `--primary` nebo `--mut`.

## Ikonografie (drž ji, je to podpis webu)
`◤` kicker před sekcí · `▲` místo/klub · `♪` umělec · `★`/`☆` sledování ·
`⇪` sdílet · `✶` oddělovač v marquee · `→` v CTA tlačítkách.

## Tlačítka
- `.btn` = mono, uppercase, `letter-spacing:.12em`, `background:transparent`.
- `.btn-pri` = plná `--primary` (hlavní akce: vstupenky, vstoupit).
- `.btn-out` = jen obrys `#5a554c` (sekundární: mapa, kalendář, sledovat, sdílet).
- Na jednom místě **max jedno** `.btn-pri`.

## Animace
Existující keyframes: `flick, scroll, aurora, grain, scan, glow, fade, view`.
- Rychlost: mikro-interakce `.15s`, přechody `.35s ease`, velké přesuny `.55s cubic-bezier(.7,0,.3,1)`.
- Přepnutí módu má vlastní choreografii (`m-out` 180 ms → render → `m-in` 470 ms) — neobcházej ji.
- Efekty (scanlines, zrno, aurora) jsou **atmosféra na pozadí**, nikdy nesmí rušit čtení.
- **Vždy respektuj** `@media(prefers-reduced-motion:reduce)` — pravidlo v CSS už existuje, nové
  animace musí spadat pod něj.

## Tón textů
Česky (primárně) i anglicky. Mluv jako člověk, co tam chodí — ne jako appka.

**Dělej:**
- Krátce, konkrétně, tykej: „Vyber si mód a najdi program na dnešní noc."
- Prázdné stavy hraj s nadhledem: „Ztracen ve scéně." (404), „Zatím nikoho nesleduješ."
- Hlášky mohou mít atmosféru scény: „Vezmi špunty.", „Respektuj prostor."
- Diakritika vždy správně. EN varianta je stručnější, ne doslovný překlad.

**Nedělej:**
- ❌ korporátní vata („Vážený uživateli", „Naše platforma vám umožňuje…")
- ❌ vykřičníky a marketingový hype („NEJLEPŠÍ AKCE!!!")
- ❌ emoji v UI (výjimka: funkční ikonka u akce, např. 📅 kalendář, 📧 mail)
- ❌ anglicismy tam, kde je česky přirozenější slovo

## Technické mantinely
- `public/index.html` uprav **cíleně malými edity**, ne přepisem celého souboru.
- Veškerý uživatelský i scrapnutý text prožeň přes `esc()` (XSS + rozbití HTML).
- Po úpravě ověř: soubor končí `</html>` a v `<script>` sedí závorky.
