---
name: grabber-test
description: Otestování grabberů a notify bez zásahu do produkce. Použij při „otestuj grabber", po úpravě grab_povrch.py / grab_underground.py / notify.py, nebo když web ukazuje divná/chybějící data. Dry-run sada + sanity výstupu, ať se na produkci nepošle nic rozbitého.
---

# Test grabberů

Vše má `--dry-run` (nic nezapíše, jen vypíše):
```bash
python grab_povrch.py --dry-run
python grab_underground.py --dry-run
python notify.py --dry-run          # nic neodešle
```

## Co kontrolovat
- **Vrací zdroj data?** GoOut POVRCH typicky ~8 akcí, underground GoOut ~6. 0 akcí pro celé Brno = zdroj nejspíš spadl (ne prázdný večer).
- Akce mají platný `date` (YYYY-MM-DD), existující `venue` id, `title`.
- `WARNINGS` prázdné (jinak některý zdroj spadl → v produkci by šel alert mail; subject „!! BRNO SCENA - grabber ALERT").

## Odolnost, kterou test hlídá
- Zápis `index.html` je atomický (`.tmp` → re-read → `os.replace`); když je výstup podezřele malý nebo bez `</html>`, **neuloží nic**.
- Úklid běží i při 0 akcí: má-li zdroj data → smaže prošlé/zmizelé auto; nemá-li → smaže jen prošlé, budoucí NECHÁ. Ručních `i` se nedotkne.
- notify páruje přes stabilní klíč `datum|venue|title` (auto-ID `a`/`u` se každý běh přečíslují).

## Reálný mail
Lokálně `notify.py` mail neodešle (chybí GMAIL secrets) — odeslání ověříš jen reálným během workflow. Šablonu laď přes [[notify-mail]]. GoOut recept → [[goout-api]].
