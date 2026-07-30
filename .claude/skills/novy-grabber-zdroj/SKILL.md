---
name: novy-grabber-zdroj
description: Přidání nového zdroje akcí do grabberu (fetch_* funkce) — další brněnský klub, festival, FB events apod. Použij při „přidej zdroj akcí", „nový klub do grabberu", rozšíření pokrytí. Drží vzor Kabinet/Alterna/Exit: fetch → parse → normalizace → dedup → resilience, aby výpadek zdroje nikdy nerozbil web ani běh.
---

# Nový zdroj akcí

Grabbery denně doplňují akce do `public/index.html`. Underground zdroje (weby klubů) žijí v `grab_underground.py` jako `fetch_*` funkce (Kabinet, Alterna, Exit) — nový zdroj kopíruje jejich vzor. GoOut je zvlášť (entity API).

## Kostra fetch_novyklub()
1. **Fetch** přes `requests` (vždy `timeout`!), parse `BeautifulSoup`. GoOut = ne HTML scraping, ale entity API → [[goout-api]].
2. **Normalizuj** na event dict: `{id, date (YYYY-MM-DD), venue, title, time, lineup[], price, ticket, genres[], mode}`.
   - `venue` = id klubu z `VENUES` (musí existovat v index.html — jinak přidej i do `V`/`VENUES`/`COORDS`, jinak deep-link spadne na 404).
   - ID prefix `u` (auto underground). Datum vždy ISO.
3. **Žánry** řeší pravidla (klíčová slova), ne AI — schválně, ať běh nestojí kredity.

## Resilience (nesahat bez rozmyslu)
- Funkce při pádu vrátí `[]`, nikdy nevyhodí výjimku (vzor `_api_get` → None).
- Při pádu zdroje přidej hlášku do `g.WARNINGS` → workflow pošle alert mail.
- Text čisti `js_escape` (newline/control/U+2028-9), **krať PŘED escapem**. Zápis index.html je atomický (`.tmp` → re-read → `os.replace`) — nesahej na to.

## Dedup
Underground dedupuje i podle `(date, venue)` — GoOut a weby klubů vracejí tytéž akce jinak pojmenované. Zapoj nový zdroj do stejného dedup kroku.

## Test
`python grab_underground.py --dry-run` (nic nezapíše) → [[grabber-test]]. Ověř správný `venue` id a datum. Editace webu → [[safe-index-edit]].
