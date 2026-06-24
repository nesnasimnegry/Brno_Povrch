#!/usr/bin/env python3
"""
grab_underground.py — UNDERGROUND varianta off-cloud grabberu.

Sdílí veškerou logiku s grab_povrch.py (parsování GoOutu, bezpečná editace
index.html), jen přepíše: jiné podniky + mode "underground" + id "u".

Bere underground akce z GoOutu (kluby, co tam mají program). Čistě DIY/sklepní
podniky, které na GoOutu nejsou, zůstávají ručně přes formulář na webu.

Pořadí běhu: nejdřív grab_povrch.py, pak tenhle (každý sahá jen na své id).

Použití:
    python grab_underground.py --dry-run
    python grab_underground.py
"""
import sys
import grab_povrch as g

# Underground podniky a jejich názvy na GoOutu (lowercase text odkazu) -> ID v appce.
# (Confirmed sety z původního underground grabberu; další DIY podniky doplníme na
#  podzim, až ověříme jejich přesné názvy na GoOutu.)
g.VENUE_MAP = {
    "kabinet múz": "kabinet", "kabinet muz": "kabinet",
    "klub alterna": "alterna", "alterna": "alterna",
    "artbar": "artbar", "druhý pád": "artbar", "artbar druhý pád": "artbar",
    "vodojemy": "vodojemy", "vodojemy žlutý kopec": "vodojemy",
    "exit club": "exit", "exit": "exit",
    "industra": "industra",
    "skleněná louka": "sklenka",
}
g.MODE = "underground"
g.ID_PREFIX = "u"
g.REPLACE_RE = r"^u"     # přepiš JEN underground auto-grab; nesahej na "a"/"i"

if __name__ == "__main__":
    sys.exit(g.main())
