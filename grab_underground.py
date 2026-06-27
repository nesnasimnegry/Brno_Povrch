#!/usr/bin/env python3
"""
grab_underground.py — UNDERGROUND grabber.

Zdroje:
  1) GoOut — underground kluby, co tam mají program (s detaily: cena, lineup).
  2) Web Kabinetu Múz — server-rendered, jeho KOMPLETNÍ program (datum v URL).
  3) Web Klubu Alterna — server-rendered (datum D.M.YYYY + název).

Akce ze všech zdrojů se spojí a odduplikují (přednost má GoOut verze s detaily;
weby klubů doplní, co na GoOutu není). Sdílí logiku s grab_povrch.py.

Použití:
    python grab_underground.py --dry-run
    python grab_underground.py
"""
import argparse
import datetime
import re
import sys

import requests
from bs4 import BeautifulSoup
import grab_povrch as g

# GoOut underground kluby (text odkazu na GoOutu -> ID v appce)
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
g.REPLACE_RE = r"^u"

KABINET_URL = "https://www.kabinetmuz.cz/program"
ALTERNA_URL = "https://www.alterna.cz/program/"
EXIT_URL = "https://www.exitclubbrno.cz/"

# Exit promuje i open-airy jinde — místo odhadni z názvu:
EXIT_VENUE_HINTS = [
    (r"valtice", None),                                    # mimo Brno -> přeskočit
    (r"špilberk|na hrad|at the castle|spilas", "spilberk"),
    (r"\bboby\b|bobyhall", "boby"),
]


def _key(e):
    return (e["date"], e["title"].lower()[:24])


def _mk(title, date, venue, ticket):
    return {
        "title": title, "date": date, "time": "20:00", "venue": venue,
        "genres": g.genre_for(title, "koncert"),
        "ticket": ticket, "price": "", "lineup": [], "blurb": title[:90], "desc": "",
    }


def fetch_kabinet(today):
    """Web Kabinetu Múz — datum z URL (/program/YYYY-MM-DD-…), název z textu odkazu."""
    out, seen = [], set()
    horizon = today + datetime.timedelta(weeks=g.WEEKS_AHEAD)
    try:
        r = requests.get(KABINET_URL, headers=g.UA, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"[warn] Kabinet web nešel načíst: {e}", file=sys.stderr)
        return out
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=re.compile(r"/program/\d{4}-\d{2}-\d{2}-")):
        m = re.search(r"/program/(\d{4}-\d{2}-\d{2})-", a.get("href", ""))
        if not m:
            continue
        date = m.group(1)
        if date < today.strftime("%Y-%m-%d") or date > horizon.strftime("%Y-%m-%d"):
            continue
        text = a.get_text(" ", strip=True)
        title = re.sub(r"^(?:DNES\s+)?\S+\s+\d{1,2}\.\s*\d{1,2}\.\s*", "", text).strip()
        if not title or "ZRUŠENO" in title.upper():
            continue
        e = _mk(title, date, "kabinet", "https://www.kabinetmuz.cz" + a.get("href", ""))
        if _key(e) in seen:
            continue
        seen.add(_key(e))
        out.append(e)
    return out


def fetch_alterna(today):
    """Web Klubu Alterna — datum D.M.YYYY u akce, název v <h3>."""
    out, seen = [], set()
    horizon = today + datetime.timedelta(weeks=g.WEEKS_AHEAD)
    try:
        r = requests.get(ALTERNA_URL, headers=g.UA, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"[warn] Alterna web nešel načíst: {e}", file=sys.stderr)
        return out
    soup = BeautifulSoup(r.text, "html.parser")
    for h in soup.find_all("h3"):
        a = h.find("a", href=re.compile(r"/program/[^/?]+/?$"))
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        href = a.get("href", "")
        if not title:
            continue
        date = None
        for da in soup.find_all("a", href=href):
            m = re.match(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", da.get_text(" ", strip=True))
            if m:
                date = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
                break
        if not date or date < today.strftime("%Y-%m-%d") or date > horizon.strftime("%Y-%m-%d"):
            continue
        ticket = ("https://www.alterna.cz" + href) if href.startswith("/") else href
        e = _mk(title, date, "alterna", ticket)
        if _key(e) in seen:
            continue
        seen.add(_key(e))
        out.append(e)
    return out


def _exit_venue(title):
    t = title.lower()
    for pat, vid in EXIT_VENUE_HINTS:
        if re.search(pat, t):
            return vid
    return "exit"


def fetch_exit(today):
    """Web Exit Clubu — techno/rave akce. Místo z názvu (Špilberk/Boby/Exit; Valtice = skip).
    Žánr RAVE/TECHNO napevno, lineup z webu."""
    out, seen = [], set()
    horizon = today + datetime.timedelta(weeks=g.WEEKS_AHEAD)
    try:
        r = requests.get(EXIT_URL, headers=g.UA, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"[warn] Exit web nešel načíst: {e}", file=sys.stderr)
        return out
    soup = BeautifulSoup(r.text, "html.parser")
    skip = re.compile(r"nadcházej|youtube|aktuality|^news$|top events|event měsíce|"
                      r"přidej se|partne|location|connect|releases|exit live|latest|"
                      r"galeri|gallery|kontakt|o nás", re.I)
    for h in soup.find_all("h2"):
        title = h.get_text(" ", strip=True)
        if not title or len(title) < 3 or skip.search(title):
            continue
        box, date, time = h, None, "20:00"
        for _ in range(4):
            if box is None:
                break
            m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})(?:\s*START\s*(\d{1,2}):(\d{2}))?",
                          box.get_text(" ", strip=True))
            if m:
                date = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
                if m.group(4):
                    time = f"{int(m.group(4)):02d}:{m.group(5)}"
                break
            box = box.parent
        if not date or date < today.strftime("%Y-%m-%d") or date > horizon.strftime("%Y-%m-%d"):
            continue
        venue = _exit_venue(title)
        if venue is None:        # mimo Brno (Valtice apod.)
            continue
        lineup, ticket = [], EXIT_URL
        if box is not None:
            for la in box.find_all("a", href=re.compile(r"/artists/")):
                nm = la.get_text(" ", strip=True)
                if nm and nm.lower() not in [x.lower() for x in lineup]:
                    lineup.append(nm)
            tk = box.find("a", href=re.compile(r"smsticket|goout\.net|facebook\.com/events"))
            if tk:
                ticket = tk.get("href", EXIT_URL)
        e = {
            "title": title, "date": date, "time": time, "venue": venue,
            "genres": ["RAVE", "TECHNO"], "ticket": ticket,
            "price": "", "lineup": lineup[:6], "blurb": title[:90], "desc": "",
        }
        if _key(e) in seen:
            continue
        seen.add(_key(e))
        out.append(e)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    today = datetime.date.today()
    print(f"[info] {today} — underground: GoOut + weby klubů…")
    goout = g.fetch_events(today)          # GoOut underground (s detaily)
    have = {_key(e) for e in goout}
    have_dv = {(e["date"], e["venue"]) for e in goout}   # stejné místo+den = táž akce
    merged = list(goout)
    counts = []
    for name, src in [("Kabinet", fetch_kabinet(today)), ("Alterna", fetch_alterna(today)), ("Exit", fetch_exit(today))]:
        c = 0
        for e in src:
            dv = (e["date"], e["venue"])
            if _key(e) in have or dv in have_dv:   # GoOut verze (s cenou/lineupem) má přednost
                continue
            have.add(_key(e))
            have_dv.add(dv)
            merged.append(e)
            c += 1
        counts.append(f"{name}: +{c}")
    merged = sorted(merged, key=lambda e: e["date"])[:g.MAX_EVENTS]
    print(f"[info] GoOut: {len(goout)}, " + ", ".join(counts) + f" → celkem {len(merged)}")
    if not merged:
        print("[warn] 0 akcí.")
        return 0
    return g.update_index(merged, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
