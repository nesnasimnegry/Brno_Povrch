#!/usr/bin/env python3
"""
grab_povrch.py — off-cloud POVRCH grabber pro BRNO SCÉNA.

Stáhne nadcházející HUDEBNÍ akce z GoOut Brno (+ web Sona, který GoOut nepokrývá
celý), namapuje na ID podniků v appce a aktualizuje `const EVENTS=[...]` v
public/index.html. Zdroje se odduplikují (GoOut má přednost — má cenu a lineup).

ŽÁDNÉ LLM, žádné tajemství. Data z veřejného GoOut entity API (JSON přes requests).
Žánry řeší pravidla (klíčová slova).

Použití:
    python grab_povrch.py --dry-run     # jen vypíše, co by doplnil (nic nemění)
    python grab_povrch.py               # zapíše změny do public/index.html

Bezpečnost: NESAHÁ na underground akce ani na ručně přidané (id "i"/"u"),
nesahá na VIMG/.jpg. Přepisuje jen public auto-grab (id "a") a staré ukázky (id "e").
Když by po úpravě chybělo </html>, NIC neuloží.
"""
import argparse
import datetime
import os
import re
import sys
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# Windows konzole (cp1250) by jinak spadla na znacích jako → … — a shodila celý běh.
# errors="replace": výpis se nikdy nesmí stát důvodem pádu grabberu.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

GOOUT_BASE = "https://goout.net/cs/brno/akce/lezjyvlkk/"
SONO_URL = "https://www.sono.cz/"    # Sono Music Club — server-rendered program (GoOut ho nepokrývá)
INDEX_FILE = "public/index.html"
WEEKS_AHEAD = 6
MAX_EVENTS = 18
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
PRAGUE = ZoneInfo("Europe/Prague")

# Přepíše underground varianta (grab_underground.py) na své hodnoty:
MODE = "public"          # mode nových akcí
ID_PREFIX = "a"          # prefix id nových akcí (povrch="a", underground="u")
REPLACE_RE = r"^[ae]"    # které existující id přepsat (povrch=auto"a"+staré"e")

# Název podniku na GoOutu (lowercase, text odkazu) -> ID v appce
VENUE_MAP = {
    "fléda": "fleda", "sono": "sono", "melodka": "melodka",
    "metro music bar": "metro", "kc semilasso": "semilasso", "semilasso": "semilasso",
    "stará pekárna": "starapekarna", "cabaret des péchés": "cabaret",
    "zoner boby hall": "boby", "bobycentrum": "boby", "boby": "boby",
    "two faces": "twofaces", "7. nebe": "sedmnebe", "caribic": "caribic",
    "yacht": "yacht", "tabarin": "tabarin", "disco xxl": "discoxxl",
    "music lab": "musiclab", "pitkin": "pitkin", "charlie's hat": "charlieshat",
    "vn club": "vnclub", "leitner": "leitner", "typos": "typos",
    "amfiteátr řečkovice": "amfik", "amfiteátr kraví hora": "kravihora",
    "špilberk": "spilberk", "teepee": "teepee",
    "galerie vaňkovka": "vankovka", "vaňkovka": "vankovka",
}

# GoOut je dnes SPA → akce bereme z interního entity API (strukturovaný JSON).
GOOUT_API = "https://goout.net/services/entities/v1"
GOOUT_CITY_BRNO = 101748109   # GoOut cityId pro Brno (serverový filtr)
# mainCategory v API, které bereme jako hudbu (divadlo/výstavy/sport ignorujeme):
MUSIC_CATEGORIES = {"concerts", "clubbing", "festivals", "parties", "dancing", "music"}
# překlad kategorie na nápovědu pro genre_for (ta zná česká/klíčová slova):
_CAT_HINT = {"clubbing": "party", "parties": "party", "dancing": "party",
             "festivals": "festival", "concerts": "koncert"}

# Self-monitoring: sem grabbery hlásí selhání zdroje (→ alert.txt → e-mail).
# Sdílí i grab_underground.py přes `import grab_povrch as g`.
WARNINGS = []


# ---------- žánry podle pravidel ----------
# GoOut žánrové tagy u akcí (event.attributes.tags) → naše zobrazované žánry.
_TAG_MAP = {
    "rock": "ROCK", "metal": "METAL", "punk": "PUNK", "hardcore": "PUNK",
    "folk": "FOLK", "folklore": "FOLK", "singer_songwriter": "FOLK", "country": "FOLK",
    "jazz_blues_swing": "JAZZ", "jazz": "JAZZ", "blues": "JAZZ", "swing": "JAZZ",
    "classical": "KLASIKA", "opera": "KLASIKA",
    "pop": "POP", "hiphop": "HIP HOP", "hip_hop": "HIP HOP", "rap": "HIP HOP",
    "electronic": "ELEKTRO", "techno": "TECHNO", "house": "HOUSE",
    "drum_and_bass": "DNB", "dnb": "DNB", "trance": "TECHNO",
    "alternative": "ALTERNATIVA", "indie": "INDIE",
    "reggae_ska": "REGGAE", "reggae": "REGGAE", "ska": "REGGAE",
    "world_music": "WORLD", "world": "WORLD",
    "experimental": "EXPERIMENT", "ambient": "EXPERIMENT", "noise": "EXPERIMENT",
    "disco": "DISKO", "funk_soul": "FUNK", "funk": "FUNK", "soul": "FUNK",
}


def event_genres(main_category, tags, title):
    """Žánry akce: přednostně z GoOut tagů (skutečné žánry), jinak heuristika z názvu."""
    out = []
    for tg in (tags or []):
        d = _TAG_MAP.get(tg)
        if d and d not in out:
            out.append(d)
    if out:
        return out[:3]
    return genre_for(title, _CAT_HINT.get(main_category, main_category))


def genre_for(title, category):
    t = (title + " " + category).lower()
    if any(k in t for k in ["techno", "house", "rave", "dnb", "drum and bass", "acid", "trance", "hardtek"]):
        tags = ["RAVE"]
        if "techno" in t:
            tags.append("TECHNO")
        elif "house" in t:
            tags.append("HOUSE")
        return tags
    if "part" in category.lower() or any(k in t for k in ["diskotéka", "disco", "párty", "open-air", "open air"]):
        return ["PÁRTY"]
    tags = ["KONCERT"]
    if any(k in t for k in ["punk", "hardcore", "metal", "screamo", "grind", "noise"]):
        tags.append("PUNK")
    elif "jazz" in t:
        tags.append("JAZZ")
    elif any(k in t for k in ["indie", "alt ", "alternativ", "rock"]):
        tags.append("INDIE")
    elif any(k in t for k in ["folk", "písničkář", "country"]):
        tags.append("FOLK")
    elif any(k in t for k in ["ambient", "drone", "experiment"]):
        tags.append("AMBIENT")
    return tags


# ---------- GoOut entity API ----------
# GoOut je dnes SPA; veřejné HTML už akce neobsahuje. Bereme je z interního
# entity API: /schedules vrací výskyty akcí (datum/čas + reference na venue,
# event a performery). Filtr na Brno řeší server (cityId), na naše podniky
# a hudbu filtrujeme až tady.

def parse_iso(s):
    """GoOut čas (ISO 8601 vč. offsetu, např. 2026-06-27T20:00:00+02:00)
    -> (YYYY-MM-DD, HH:MM) v čase Prahy."""
    s = (s or "").strip().replace("Z", "+00:00")
    try:
        d = datetime.datetime.fromisoformat(s)
    except ValueError:
        return None, None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    d = d.astimezone(PRAGUE)
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M")


def _api_get(path, params):
    """GET na GoOut entity API. Vrátí dict, při JAKÉKOLI chybě None (nikdy
    nevyhodí výjimku) — výpadek zdroje nesmí shodit grabber ani web."""
    base = [("languages[]", "cs"), ("source", "goout.net")]
    try:
        r = requests.get(f"{GOOUT_API}/{path}", params=base + params,
                         headers={**UA, "Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[warn] GoOut API /{path} selhalo: {e}", file=sys.stderr)
        return None


def _fetch_entities(path, ids):
    """Dotáhne entity (venues/events/performers) podle ID. Vrátí {str(id): entity}.
    ID se posílají jako opakované ids[] (po 25)."""
    out = {}
    ids = [str(i) for i in ids]
    for i in range(0, len(ids), 25):
        j = _api_get(path, [("ids[]", x) for x in ids[i:i + 25]])
        for e in (j or {}).get(path, []) or []:
            out[str(e.get("id"))] = e
    return out


def _locale_name(entity):
    cs = (entity.get("locales") or {}).get("cs") or {}
    return (cs.get("name") or "").strip()


def _venue_app_id(goout_name):
    """Název podniku z GoOutu -> ID v appce. Nejdřív přesně, pak podřetězcem
    (GoOut má 'Klub Fléda', my klíč 'fléda')."""
    n = goout_name.lower().strip()
    if n in VENUE_MAP:
        return VENUE_MAP[n]
    for key, vid in VENUE_MAP.items():
        if key in n:
            return vid
    return None


def _pricing_str(pricing):
    """GoOut 'pricing' ('190–300' / '0' / None) -> text ceny pro kartu."""
    p = (pricing or "").strip()
    if not p:
        return ""
    if set(p) <= set("0–- "):
        return "Zdarma"
    return f"{p} Kč"


# Promotéři (hlavně Exit) dělají akce jinde, než sídlí → GoOut je vede pod domovským
# klubem. Podle názvu srovnej na skutečné místo konání. Sdílené i grab_underground.py.
VENUE_TITLE_HINTS = [
    (r"na hrad|at the castle|špilberk|spilberk|spilas", "spilberk"),
    (r"\bboby\b|boby ?hall|bobycentrum", "boby"),
    (r"vaňkov|vankov", "vankovka"),
]


def correct_venue(title, venue):
    t = (title or "").lower()
    for pat, vid in VENUE_TITLE_HINTS:
        if re.search(pat, t):
            return vid
    return venue


def fetch_events(today):
    horizon = today + datetime.timedelta(weeks=WEEKS_AHEAD)
    today_s, horizon_s = today.strftime("%Y-%m-%d"), horizon.strftime("%Y-%m-%d")

    # 1) Posbírej brněnské schedules (stránkování přes meta.nextScrollId).
    schedules, scroll, pages = [], None, 0
    while pages < 20:
        params = [("cityIds[]", str(GOOUT_CITY_BRNO)), ("limit", "60")]
        if scroll:
            params.append(("scrollId", scroll))
        j = _api_get("schedules", params)
        batch = (j or {}).get("schedules") or []
        if not batch:
            break
        schedules += batch
        pages += 1
        scroll = (j.get("meta") or {}).get("nextScrollId")
        last = ((batch[-1].get("attributes") or {}).get("startAt") or "")[:10]
        if not scroll or (last and last > horizon_s):
            break
    if not schedules:
        WARNINGS.append(f"GoOut entity API vrátilo 0 schedules pro celé Brno (cityId {GOOUT_CITY_BRNO}) "
                        f"— pravděpodobně změna/blok API, ne jen málo akcí.")
        print("[error] GoOut API nevrátil žádné schedules", file=sys.stderr)
        return []

    # 2) Vyber schedules v horizontu a s vazbou na venue+event; posbírej ID.
    rel = []
    for s in schedules:
        a = s.get("attributes") or {}
        date = (a.get("startAt") or "")[:10]
        if not date or date < today_s or date > horizon_s:
            continue
        r = s.get("relationships") or {}
        vid = (r.get("venue") or {}).get("id")
        eid = (r.get("event") or {}).get("id")
        if vid and eid:
            rel.append((s, str(vid), str(eid)))
    if not rel:
        return []

    venues = _fetch_entities("venues", {v for _, v, _ in rel})
    events = _fetch_entities("events", {e for _, _, e in rel})
    perf_ids = set()
    for ev in events.values():
        for p in (ev.get("relationships") or {}).get("performers") or []:
            if p.get("id"):
                perf_ids.add(str(p["id"]))
    performers = _fetch_entities("performers", perf_ids) if perf_ids else {}

    # 3) Sestav akce: jen naše podniky (VENUE_MAP) + hudba (mainCategory).
    out, seen = [], set()
    for s, vid, eid in rel:
        venue, event = venues.get(vid), events.get(eid)
        if not venue or not event:
            continue
        app_venue = _venue_app_id(_locale_name(venue))
        if not app_venue:
            continue
        cat = (event.get("attributes") or {}).get("mainCategory") or ""
        if cat not in MUSIC_CATEGORIES:
            continue
        title = _locale_name(event)
        if not title:
            continue
        date, time = parse_iso((s.get("attributes") or {}).get("startAt"))
        if not date:
            continue
        key = (title.lower(), date)
        if key in seen:
            continue
        seen.add(key)
        lineup = []
        for p in (event.get("relationships") or {}).get("performers") or []:
            nm = _locale_name(performers.get(str(p.get("id")), {}))
            if nm and nm not in lineup:
                lineup.append(nm)
        desc = ((event.get("locales") or {}).get("cs") or {}).get("description") or ""
        desc = re.sub(r"\s+", " ", desc).strip()[:240]
        blurb = (re.split(r"(?<=[.!?])\s", desc)[0][:90] if desc else title[:90])
        out.append({
            "title": title, "date": date, "time": time, "venue": correct_venue(title, app_venue),
            "genres": event_genres(cat, (event.get("attributes") or {}).get("tags"), title),
            "ticket": s.get("url") or GOOUT_BASE, "category": cat,
            "price": _pricing_str((s.get("attributes") or {}).get("pricing")),
            "lineup": lineup[:6], "blurb": blurb, "desc": desc,
        })
    out.sort(key=lambda e: e["date"])
    return out[:MAX_EVENTS]


# ---------- práce s index.html ----------
def js_escape(s):
    # Pozn.: po escapu NEKRÁTIT (uříznutý '\' rozbije literál) — krať RAW text PŘED voláním.
    s = str(s).replace("\\", "\\\\").replace('"', '\\"')
    # Znaky, které jinak rozbijí JS string literál → SyntaxError → bílá obrazovka pro všechny:
    s = s.replace("\u2028", " ").replace("\u2029", " ")   # JS radkove oddelovace
    s = re.sub(r"[\x00-\x1f]+", " ", s)                    # newline, tab, ostatní control znaky
    return s


def split_items(arr_body):
    """Rozseká tělo JS pole na top-level {...} položky (ignoruje závorky v řetězcích)."""
    items, depth, start, in_str, q, esc = [], 0, None, False, "", False
    for i, ch in enumerate(arr_body):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == q:
                in_str = False
            continue
        if ch in '"\'':
            in_str, q = True, ch
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                items.append(arr_body[start:i + 1])
                start = None
    return items


def item_id(item):
    m = re.search(r'id\s*:\s*"([^"]+)"', item)
    return m.group(1) if m else ""


def item_date(item):
    m = re.search(r'date\s*:\s*"([^"]*)"', item)
    return m.group(1) if m else ""


def _norm_title(t):
    """Název pro porovnání: bez závorek (USA)/(SK), bez interpunkce, jen slova+čísla."""
    t = re.sub(r"\([^)]*\)", " ", (t or "").lower())
    t = re.sub(r"[^\w ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _same_event(t1, t2):
    """Táž akce z jiného zdroje? Fuzzy: shodný normalizovaný název, nebo kratší je
    (dostatečně dlouhým) podřetězcem delšího ('EXIT At The Castle' ⊂ '…| Joris Voorn')."""
    a, b = _norm_title(t1), _norm_title(t2)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 10 and short in long


def build_item(idx, e):
    feat = "true" if idx <= 2 else "false"
    genres = ",".join(f'"{g}"' for g in e["genres"])
    lineup = ",".join('"%s"' % js_escape(x) for x in e.get("lineup", []))
    price = js_escape(e.get("price") or "vstupenky na GoOut")
    blurb = js_escape((e.get("blurb") or e["title"])[:90])   # krátit PŘED escapem (jinak uříznutý \")
    desc = js_escape((e.get("desc") or "")[:240])
    return (
        '{id:"%s%d",mode:"%s",title:"%s",date:"%s",time:"%s",venue:"%s",'
        'genres:[%s],price:"%s",ticket:"%s",featured:%s,'
        'lineup:[%s],blurb:"%s",desc:"%s"}'
        % (ID_PREFIX, idx, MODE, js_escape(e["title"]), e["date"], e["time"], e["venue"],
           genres, price, js_escape(e["ticket"]), feat, lineup, blurb, desc)
    )


def update_index(events, dry_run):
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"const EVENTS=\[", src)
    if not m:
        print("[error] v index.html není 'const EVENTS=['", file=sys.stderr)
        return 1
    start = m.end() - 1  # index '['
    depth, in_str, q, esc, end = 0, False, "", False, None
    for i in range(start, len(src)):
        ch = src[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == q:
                in_str = False
            continue
        if ch in '"\'':
            in_str, q = True, ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        print("[error] nenašel jsem konec pole EVENTS", file=sys.stderr)
        return 1
    items = split_items(src[start + 1:end])
    kept = [it for it in items if not re.match(REPLACE_RE, item_id(it))]
    today_s = datetime.date.today().strftime("%Y-%m-%d")
    if events:
        # Zdroj dodal akce → nahraď celý auto-blok čerstvými (jen budoucími);
        # prošlé i zmizelé auto-akce tím samy zmizí.
        # Dedup proti ostatním akcím (druhý grabber + ruční) — fuzzy podle názvu na stejné datum.
        # Chytá i cross-grabber duplikáty (POVRCH "a" × underground "u" na sdíleném Špilberk/Boby).
        existing_by_date = {}
        for it in kept:
            tt = re.search(r'title\s*:\s*"([^"]*)"', it)
            dd = re.search(r'date\s*:\s*"([^"]*)"', it)
            if tt and dd:
                existing_by_date.setdefault(dd.group(1), []).append(tt.group(1))
        fresh = [e for e in events
                 if not any(_same_event(e["title"], x) for x in existing_by_date.get(e["date"], []))]
        auto_block = [build_item(i + 1, e) for i, e in enumerate(fresh)]
        info = (f"doplněno {len(auto_block)} {MODE} "
                f"({len(events) - len(fresh)} přeskočeno jako duplikát)")
    else:
        # Zdroj nic nedodal (možná spadl) → NEMAž budoucí auto-akce, jen prošlé.
        old_auto = [it for it in items if re.match(REPLACE_RE, item_id(it))]
        auto_block = [it for it in old_auto if item_date(it) >= today_s]
        fresh = []
        info = (f"zdroj prázdný — zachováno {len(auto_block)} budoucích auto, "
                f"smazáno {len(old_auto) - len(auto_block)} prošlých")
    new_src = src[:start + 1] + "\n" + ",\n".join(kept + auto_block) + "\n" + src[end:]
    if new_src.count("</html>") != 1:
        print("[error] po úpravě není právě jedno </html> — NEUKLÁDÁM", file=sys.stderr)
        return 1
    if len(new_src) < len(src) // 2:
        print(f"[error] výsledek podezřele malý ({len(new_src)} vs {len(src)} B) — NEUKLÁDÁM", file=sys.stderr)
        return 1
    print(f"[info] ponecháno {len(kept)} ostatních, {info}")
    if dry_run:
        print("[dry-run] nic se nezapsalo. Nové akce:")
        for e in fresh:
            lu = (" · " + ", ".join(e.get("lineup", []))) if e.get("lineup") else ""
            print(f"   {e['date']} {e['time']}  {e['venue']:12s} {'/'.join(e['genres']):12s} {(e.get('price') or ''):12s} {e['title']}{lu}")
        return 0
    if new_src == src:
        print("[info] beze změny — nezapisuji.")
        return 0
    # Atomický zápis: do .tmp, ověř re-readem celistvost, teprve pak os.replace.
    # Když proces umře uprostřed zápisu, live index.html zůstane nedotčený.
    tmp = INDEX_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new_src)
    with open(tmp, "r", encoding="utf-8") as f:
        written = f.read()
    if written != new_src or written.count("</html>") != 1:
        os.remove(tmp)
        print("[error] zapsaný soubor nesouhlasí (neúplný zápis?) — PŮVODNÍ index.html ZACHOVÁN", file=sys.stderr)
        return 1
    os.replace(tmp, INDEX_FILE)
    print(f"[ok] {INDEX_FILE} zapsán ({len(new_src)} znaků).")
    if fresh:
        with open("report.txt", "a", encoding="utf-8") as rf:
            rf.write(f"\n— {MODE.upper()} — doplněno {len(fresh)} akcí:\n")
            for e in fresh:
                lu = (" — " + ", ".join(e.get("lineup", []))) if e.get("lineup") else ""
                rf.write(f"  • {e['date']} {e['time']}  {e['venue']}  [{'/'.join(e['genres'])}]  "
                         f"{e.get('price') or ''}  {e['title']}{lu}\n")
    return 0


def write_alerts(dry_run):
    """Self-monitoring: nasbírané WARNINGS zapíše do alert.txt (workflow je pošle mailem)."""
    if not WARNINGS:
        return
    for w in WARNINGS:
        print(f"[ALERT] {w}", file=sys.stderr)
    if not dry_run:
        with open("alert.txt", "a", encoding="utf-8") as af:
            af.write(f"\n⚠️ {MODE.upper()} — {datetime.date.today()}:\n")
            for w in WARNINGS:
                af.write(f"  • {w}\n")


def fetch_sono(today):
    """Web Sono Music Clubu — server-rendered seznam akcí.

    Karta = a[href*=/event/] + nejbližší nadpis (h1–h4) + datum D.M.YYYY v textu.
    Každá akce je na stránce 2× (odkaz na detail + kotva #vstupenka) → href se
    normalizuje (bez fragmentu/query) a dedupuje. Resilience jako ostatní zdroje:
    při pádu vrátí [] a zapíše WARNING (běh se nezastaví)."""
    out, seen = [], set()
    horizon = today + datetime.timedelta(weeks=WEEKS_AHEAD)
    lo, hi = today.strftime("%Y-%m-%d"), horizon.strftime("%Y-%m-%d")
    try:
        r = requests.get(SONO_URL, headers=UA, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"[warn] Sono web nešel načíst: {e}", file=sys.stderr)
        WARNINGS.append(f"Sono web nešel načíst: {e}")
        return out
    soup = BeautifulSoup(r.text, "html.parser")
    date_re = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d\d)")
    for a in soup.select('a[href*="/event/"]'):
        href = a.get("href", "").split("#")[0].split("?")[0]
        if not href or href in seen:
            continue
        card, title, date = a, None, None
        for _ in range(4):
            card = card.parent
            if card is None:
                break
            h = card.find(["h1", "h2", "h3", "h4"])
            if h and not title:
                title = re.sub(r"\s+", " ", h.get_text(" ", strip=True)).strip()
            m = date_re.search(card.get_text(" ", strip=True))
            if m and not date:
                date = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
            if title and date:
                break
        if not title or not date or date < lo or date > hi:
            continue
        seen.add(href)
        out.append({
            "title": title, "date": date, "time": "20:00", "venue": "sono",
            "genres": genre_for(title, "koncert"),
            "ticket": href, "price": "", "lineup": [], "blurb": title[:90], "desc": "",
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="jen vypsat, nic nezapisovat")
    args = ap.parse_args()
    today = datetime.date.today()
    print(f"[info] {today} — stahuji GoOut Brno + Sono…")
    goout = fetch_events(today)
    # Sono doplní, co GoOut nemá; při shodě má přednost GoOut (má detaily: cena, lineup).
    have_dv = {(e["date"], e["venue"]) for e in goout}
    titles_by_date = {}
    for e in goout:
        titles_by_date.setdefault(e["date"], []).append(e["title"])
    events, added = list(goout), 0
    for e in fetch_sono(today):
        if (e["date"], e["venue"]) in have_dv or \
           any(_same_event(e["title"], t) for t in titles_by_date.get(e["date"], [])):
            continue
        have_dv.add((e["date"], e["venue"]))
        titles_by_date.setdefault(e["date"], []).append(e["title"])
        events.append(e)
        added += 1
    events = sorted(events, key=lambda e: e["date"])[:MAX_EVENTS]
    print(f"[info] GoOut {len(goout)} + Sono +{added} → celkem {len(events)} akcí.")
    if not events:
        print("[warn] 0 akcí v našich podnicích — uklidím prošlé auto-akce, budoucí nechám.")
    rc = update_index(events, args.dry_run)   # běží i při 0 akcí → úklid prošlých
    write_alerts(args.dry_run)
    return rc


if __name__ == "__main__":
    sys.exit(main())
