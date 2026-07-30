---
name: seo-klub-stranka
description: Nová SEO stránka klubu (klub-*.html) s JSON-LD MusicVenue, konzistentní s existujícími ~40. Použij při „přidej klub", „SEO stránka pro <klub>", rozšíření organického dosahu. Drží strukturu a vizuál ostatních klub-stránek + brno-styl.
---

# SEO stránka klubu

`public/klub-*.html` = ~40 samostatných SEO stránek (JSON-LD `MusicVenue`), oddělené od SPA kvůli indexovatelnosti (SPA obsah Google hůř čte). Nová stránka kopíruje existující.

## Postup
1. Vezmi existující `public/klub-*.html` jako šablonu (stejný layout, meta, JSON-LD kostra) — konzistence > vymýšlení nového.
2. Vyplň: název, adresu, `geo` (z `COORDS` v index.html), popis, odkaz zpět do appky (`#/klub/<id>`).
3. **JSON-LD `MusicVenue`**: `@type:"MusicVenue"`, `name`, `address` (`PostalAddress`, Brno, CZ), `geo` (`GeoCoordinates`), `url`.
4. Klub musí existovat i v datech appky: `V`/`VENUES`, `COORDS`, případně `VIMG` (fotka) — jinak deep-link `#/klub/<id>` spadne na 404.
5. Vizuál a tón → [[brno-styl]]. Přidej URL do `public/sitemap.xml`.

## Ověř
Validuj JSON-LD (Google Rich Results Test). Deploy → [[deploy-verify]]. Editace webu → [[safe-index-edit]].
