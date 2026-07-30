---
name: og-karta
description: Vlastní brandovaná OG/social sdílecí karta (1200×630) a její zapojení do meta tagů. Použij při „OG karta", „náhled sdílení", „jak to vypadá na FB/Twitteru/Messengeru", nebo když social preview tahá generickou/cizí fotku. Karta drží vizuální jazyk módů (viz brno-styl).
---

# OG / social karta

Sdílený odkaz teď tahá generickou Unsplash fotku (`og:image` v `<head>` `public/index.html`). Portfolio produkt chce vlastní hostovanou brandovanou kartu — spolehlivost (Unsplash může zmizet) + brand.

## Zadání karty
- Rozměr **1200×630** (FB/Twitter `summary_large_image`).
- Vizuální jazyk viz [[brno-styl]]: tmavé pozadí `#0c0b0a`, mono labely, kicker `◤`, název BRNO SCÉNA / BRNO PODZEMÍ / POVRCH. Klidně motiv obou módů (žlutá `#ecc400` + cyan `#37d4e6`).
- Ulož do `public/` (např. `public/og.jpg`), optimalizuj (JPG, ~<200 KB).

## Zapojení
V `<head>` `public/index.html` přepiš absolutními URL (scrapery FB/Twitteru relativní neberou):
```html
<meta property="og:image" content="https://snabba.pages.dev/og.jpg" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta name="twitter:image" content="https://snabba.pages.dev/og.jpg" />
```

## Ověření
Deploy ([[deploy-verify]]) → otestuj přes FB Sharing Debugger / Twitter Card Validator („Scrape Again" protlačí cache scraperu). Editace souboru přes [[safe-index-edit]].
