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
import json
import os
import re
import sys
import time
import unicodedata

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
        g.WARNINGS.append(f"Kabinet web nešel načíst: {e}")
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
        g.WARNINGS.append(f"Alterna web nešel načíst: {e}")
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
        g.WARNINGS.append(f"Exit web nešel načíst: {e}")
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


# ------------------------------------------------------------------ Instagram
# Underground akce z IG postů kurátorovaných klubů. ZDARMA, ale vyžaduje PŘIHLÁŠENOU
# session (IG blokuje anonym i cloud IP). Lokálně: ig_session.py (import z prohlížeče)
# uloží session → ig_local.py scrapne z domácí IP a pushne cache → cloud ji roznese.
# Pozn.: web_profile_info je u IG rozbitý ("laser.provider" 400), proto jedeme přes
# privátní mobilní API (usernameinfo + feed/user) s hlavičkou X-IG-App-ID.
IG_CACHE = "data/ig_events.json"     # sticky: akce vydrží, i když IG zrovna blokne
IG_MAX_POSTS = 8                     # kolik posledních postů na účet
IG_LOOKBACK_DAYS = 35                # jak staré posty ještě číst
IG_APP_UA = ("Instagram 309.0.0.40.113 Android (30/11; 420dpi; 1080x2400; "
             "samsung; SM-G991B; o1s; exynos2100; en_US; 541134564)")
IG_HEADERS = {"User-Agent": IG_APP_UA, "X-IG-App-ID": "936619743392459", "X-ASBD-ID": "198387"}
# IG účet -> venue id. Klubové účty mají pevné místo; promotéři = None (venue se
# detekuje z popisku, viz _ig_venue). MAJITELI: uprav dle reálných @ / míst.
IG_ACCOUNTS = {
    # kluby (pevné místo)
    "perpetuumklub": "perpetuum",
    "perpetuum_techno_thursday": "perpetuum",
    "perpetuumdnbwednesday": "perpetuum",
    "fraktal_noise": "fraktal",
    "klub_alterna": "alterna",
    "artbar.club": "artbar",
    # promotéři (místo z popisku)
    "bassproof": None,
    "raisethebass_rave": None,
    "brnoparties": None,
    "wednesrave_brno": None,
    "brnoraves": None,
    "kpromotions.cz": None,
    "bestevents": None,
}
# klíčové slovo v popisku -> venue id (underground). Klíče bez diakritiky, malými.
VENUE_KW = {
    "perpetuum": "perpetuum", "fraktal": "fraktal", "alterna": "alterna",
    "artbar": "artbar", "art bar": "artbar", "kabinet": "kabinet", "exit club": "exit",
    "industra": "industra", "radost": "radost", "vibe": "vibe", "pulpit": "pulpit",
    "pul.pit": "pulpit", "mala amerika": "malaamerika", "mosilana": "mosilana",
    "sibir": "sibir", "sklenen": "sklenka", "sklenka": "sklenka", "vodojem": "vodojemy",
    "enter club": "enter",
}
_IG_LETTER = re.compile(r"[a-zžščřďťňáéíóúůě]", re.I)
_CZ_MONTHS = {"ledna": 1, "unora": 2, "brezna": 3, "dubna": 4, "kvetna": 5, "cervna": 6,
              "cervence": 7, "srpna": 8, "zari": 9, "rijna": 10, "listopadu": 11, "prosince": 12}
_CZ_MONTH_RE = re.compile(r"\b([0-3]?\d)\.?\s+(" + "|".join(_CZ_MONTHS) + r")(?:\s+(20\d\d))?")


def _strip(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


def _ig_venue(text, default):
    """Zkusí najít v popisku známé underground místo; jinak vrátí default (může být None)."""
    low = _strip(text)
    for kw, vid in VENUE_KW.items():
        if kw in low:
            return vid
    return default


def _parse_ig_caption(text, default_venue, today, horizon):
    """Z popisku IG postu zkusí akci. Vrátí event dict, nebo None (chybí datum/místo/horizont)."""
    if not text:
        return None
    m = re.search(r"\b([0-3]?\d)\s*\.\s*([01]?\d)\.?\s*(20\d\d)?", text)
    if m:
        d, mo, yr = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        mw = _CZ_MONTH_RE.search(_strip(text))     # "15. srpna 2026" / "15 srpna"
        if not mw:
            return None
        d, mo, yr = int(mw.group(1)), _CZ_MONTHS[mw.group(2)], mw.group(3)
    if not (1 <= d <= 31 and 1 <= mo <= 12):
        return None
    y = int(yr) if yr else today.year
    try:
        dt = datetime.date(y, mo, d)
        if not yr and dt < today:
            dt = datetime.date(y + 1, mo, d)
    except ValueError:
        return None
    if dt < today or dt > horizon:
        return None
    tm = re.search(r"\b([0-2]?\d)[:.h]([0-5]\d)\b", text)
    tstr = f"{int(tm.group(1)):02d}:{tm.group(2)}" if tm and int(tm.group(1)) < 24 else "20:00"
    raw = ""
    for ln in text.split("\n"):
        ln = re.sub(r"^[^\w]+", "", ln.strip())          # osekej vedoucí emoji/symboly
        if len(ln) >= 4 and _IG_LETTER.search(ln) and not re.match(r"^[\d.\s:h]+$", ln):
            raw = ln
            break
    if not raw:
        raw = re.sub(r"^[^\w]+", "", text.strip())
    # usekni u 1. výrazného oddělovače (název akce/interpreta bývá na začátku)
    cut = re.split(r"\s[–—|]\s|\s-\s|\s/\s|:\s", raw, 1)[0].strip()
    title = cut if len(cut) >= 4 else raw
    # osekni vedoucí datum/čas ("15. 8.", "od 22:00")
    title = (re.sub(r"^(od\s+)?(\d{1,2}\.\s*\d{1,2}\.\s*(20\d\d)?|\d{1,2}[:h]\d{2})[\s–—-]*", "", title, flags=re.I).strip()
             or title)[:80]
    if not title:
        return None
    venue = _ig_venue(text, default_venue)
    if not venue:
        return None   # promotér bez rozpoznaného místa → nelze zařadit
    return {"title": title, "date": dt.strftime("%Y-%m-%d"), "time": tstr, "venue": venue,
            "genres": g.genre_for(text[:160], "koncert"), "ticket": "", "price": "",
            "lineup": [], "blurb": title[:90], "desc": ""}


def fetch_instagram(today, dry_run=False):
    """Akce z IG postů (viz IG_ACCOUNTS). Sticky cache: nalezená akce vydrží přes výpadky IG.
    Resilience: každý účet i celý IG selže bezpečně (→ WARNINGS, vrátí aspoň cache)."""
    horizon = today + datetime.timedelta(weeks=g.WEEKS_AHEAD)
    today_s = today.strftime("%Y-%m-%d")
    try:
        cache = json.load(open(IG_CACHE, encoding="utf-8"))
    except Exception:
        cache = {}
    cache = {k: v for k, v in cache.items() if isinstance(v, dict) and v.get("date", "") >= today_s}

    try:
        import instaloader
    except ImportError:
        print("[warn] instaloader chybí — IG přeskočeno", file=sys.stderr)
        return list(cache.values())

    # max_connection_attempts=1 → na 429 nezkouší znovu (jinak by čekal ~11 min a visel workflow)
    L = instaloader.Instaloader(download_pictures=False, download_videos=False,
                                download_comments=False, save_metadata=False,
                                compress_json=False, quiet=True,
                                max_connection_attempts=1, request_timeout=20.0)
    user = os.environ.get("IG_USER")
    if not user:
        print("[warn] IG: chybí IG_USER (přihlášená session) — přeskočeno", file=sys.stderr)
        return list(cache.values())
    try:
        L.load_session_from_file(user)
        print(f"[info] IG: session '{user}' načtena", file=sys.stderr)
    except Exception as e:
        print(f"[warn] IG: session '{user}' nenačtena ({type(e).__name__}) — přeskočeno", file=sys.stderr)
        return list(cache.values())
    s = L.context._session
    s.headers.update(IG_HEADERS)   # web_profile_info je rozbitý → privátní mobilní API

    cutoff = time.time() - IG_LOOKBACK_DAYS * 86400
    found, fails = 0, 0
    for handle, venue in IG_ACCOUNTS.items():
        try:
            info = s.get(f"https://i.instagram.com/api/v1/users/{handle}/usernameinfo/", timeout=20)
            info.raise_for_status()
            pk = info.json()["user"]["pk"]
            feed = s.get(f"https://i.instagram.com/api/v1/feed/user/{pk}/?count={IG_MAX_POSTS}", timeout=20)
            feed.raise_for_status()
            for it in feed.json().get("items", []):
                ts = it.get("taken_at") or 0
                if ts and ts < cutoff:
                    break
                ev = _parse_ig_caption((it.get("caption") or {}).get("text") or "", venue, today, horizon)
                if ev:
                    ev["ticket"] = f"https://www.instagram.com/p/{it.get('code')}/"
                    cache[f'{ev["date"]}|{ev["venue"]}'] = ev   # 1 akce na místo+den (sloučí promo-duplicity)
                    found += 1
            fails = 0
            time.sleep(2)  # buď hodný na rate-limit
        except Exception as e:
            # selhání = normální (IG se brání) → NEalertuj, jen zaloguj; cache drží dřívější.
            print(f"[warn] IG @{handle}: {type(e).__name__}: {str(e)[:70]}", file=sys.stderr)
            fails += 1
            if fails >= 3:
                print("[warn] IG: 3× po sobě chyba — končím (blok/rate-limit)", file=sys.stderr)
                break
            continue

    if not dry_run:
        try:
            os.makedirs("data", exist_ok=True)
            json.dump(cache, open(IG_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception as e:
            print(f"[warn] IG cache zápis selhal: {e}", file=sys.stderr)
    print(f"[info] IG: nově {found}, v cache celkem {len(cache)}", file=sys.stderr)
    return list(cache.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    today = datetime.date.today()
    print(f"[info] {today} — underground: GoOut + weby klubů…")
    goout = g.fetch_events(today)          # GoOut underground (s detaily)
    have_dv = {(e["date"], e["venue"]) for e in goout}   # stejné místo+den = táž akce
    titles_by_date = {}                                  # datum -> [názvy] pro fuzzy dedup
    for e in goout:
        titles_by_date.setdefault(e["date"], []).append(e["title"])
    merged = list(goout)
    counts = []
    for name, src in [("Kabinet", fetch_kabinet(today)), ("Alterna", fetch_alterna(today)),
                      ("Exit", fetch_exit(today)), ("Instagram", fetch_instagram(today, args.dry_run))]:
        c = 0
        for e in src:
            # Duplikát vůči už zařazeným? Fuzzy název NEBO stejné místo+den. GoOut má přednost.
            if (e["date"], e["venue"]) in have_dv or \
               any(g._same_event(e["title"], t) for t in titles_by_date.get(e["date"], [])):
                continue
            have_dv.add((e["date"], e["venue"]))
            titles_by_date.setdefault(e["date"], []).append(e["title"])
            merged.append(e)
            c += 1
        counts.append(f"{name}: +{c}")
    merged = sorted(merged, key=lambda e: e["date"])[:g.MAX_EVENTS]
    print(f"[info] GoOut: {len(goout)}, " + ", ".join(counts) + f" → celkem {len(merged)}")
    if not merged:
        print("[warn] 0 akcí — uklidím prošlé underground akce, budoucí nechám.")
    rc = g.update_index(merged, args.dry_run)   # běží i při 0 → úklid prošlých
    g.write_alerts(args.dry_run)
    return rc


if __name__ == "__main__":
    sys.exit(main())
