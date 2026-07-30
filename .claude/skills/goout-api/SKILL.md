---
name: goout-api
description: Recept na GoOut entity API — zdroj POVRCH akcí a části underground. Použij při jakékoli práci s GoOut daty v grab_povrch.py / grab_underground.py (přidání polí, ladění, debug prázdného výstupu). GoOut je Vue SPA, HTML scraping je mrtvý — jede se přes interní JSON entity API.
---

# GoOut entity API

**Ne HTML scraping** (GoOut = Vue SPA, staré selektory mrtvé). Interní entity API vrací čistý JSON. Neoficiální → může se měnit, ale řádově stabilnější než HTML; `_api_get` selže bezpečně (vrátí None).

## Seznam akcí (schedules)
```
GET https://goout.net/services/entities/v1/schedules
    ?languages[]=cs&source=goout.net&cityIds[]=101748109
```
`101748109` = Brno. Stránkování: odpověď má `meta.nextScrollId` → další stránka přes param `scrollId`.

## Detaily entit
Dotáhni přes `/venues`, `/events`, `/performers` s **opakovaným `ids[]`** (po 25, NE čárkou):
```
GET .../v1/events?ids[]=1&ids[]=2&...      # max 25 na dotaz
```

## Mapování polí
- Název: `locales.cs.name` (ne top-level).
- Hudba: `attributes.mainCategory ∈ {concerts, clubbing, festivals, parties, dancing}`.
- Cena: `attributes.pricing`. Lineup: `relationships.performers`. Vstupenky: `url` ze schedule.

## Odolnost
`_api_get` při chybě → None → výpadek API nikdy nevyhodí výjimku (drží resilience). JSON-LD byla slepá ulička (9 promo akcí, 0 našich venue) — nevracej se k HTML selektorům. Nový klubový zdroj (ne GoOut) → [[novy-grabber-zdroj]]. Test → [[grabber-test]].
