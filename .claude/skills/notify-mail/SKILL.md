---
name: notify-mail
description: Práce na HTML notifikačním e-mailu odběratelům (notify.py build_email/_event_card). Použij při úpravě šablony mailu — layout, hlavička, karta akce, fotka klubu, texty, předmět. Drží omezení HTML mailů (table layout, inline styly) a vizuál BRNO SCÉNY.
---

# Notifikační e-mail

`notify.py` páruje nové akce ↔ odběratele a posílá mail. Šablona je oddělená v `build_email(to, token, evs)` → vrací `(subject, html)`, kartu akce dělá `_event_card(e)`. Odděleno od odesílání (`send_mail`) kvůli náhledu.

## Omezení HTML mailů (Gmail/Outlook/Apple)
- **Table-based layout**, `role="presentation"`, žádný flexbox/grid.
- **Všechny styly inline** (`style="..."`) — `<style>` blok klienti ořezávají.
- Tmavé pozadí `#0c0b0a`, mono přes `'Courier New',monospace` (web fonty v mailu nejedou).
- Absolutní URL u všeho. Text přes `html.escape`.

## Struktura (drž ji)
Hlavička `◤ TVÁ SCÉNA V BRNĚ` + BRNO SCÉNA → intro → karty (`_event_card`: datumový odznak den/měsíc, název, `▲ venue`, žánry + cena, VSTUPENKY link) → CTA `CELÝ PROGRAM →` → footer s odhlášením (`/unsubscribe?e=...&t=...`). Vizuál/tón → [[brno-styl]]. `venue_names()` mapuje venue id → hezký název — používej.

## Nápady dál
- Fotka klubu `VIMG` do karty (pozor na hostování + velikost, ať mail nenabobtná).

## Test
Náhled: zavolej `build_email(...)` a ulož HTML do souboru, otevři v prohlížeči. **Reálné odeslání jen přes GitHub workflow** (lokálně chybí GMAIL secrets). Viz [[grabber-test]].
