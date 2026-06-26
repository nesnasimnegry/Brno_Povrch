#!/usr/bin/env python3
"""
grab_povrch.py — off-cloud POVRCH grabber pro BRNO SCÉNA.

Stáhne nadcházející HUDEBNÍ akce z GoOut Brno, namapuje na ID podniků v appce
a aktualizuje pole `const EVENTS=[...]` v public/index.html.

ŽÁDNÉ LLM, žádné API, žádné tajemství. Jen requests + BeautifulSoup.
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
import re
import sys
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

GOOUT_BASE = "https://goout.net/cs/brno/akce/lezjyvlkk/"
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
    "amfiteátr řečkovice": "amfik", "špilberk": "spilberk", "teepee": "teepee",
    "galerie vaňkovka": "vankovka", "vaňkovka": "vankovka",
}

# Kategorie GoOutu, které bereme (hudba). Divadlo, Jiné akce, Výstavy... ignorujeme.
MUSIC_CATS = {"koncerty", "parties", "party", "festivaly", "kluby", "koncert"}


# ---------- žánry podle pravidel ----------
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


# ---------- parsování GoOutu ----------
def parse_iso(s):
    """GoOut <time datetime="2026-06-24T18:00:00.000Z"> (UTC) -> (YYYY-MM-DD, HH:MM) v čase Prahy."""
    s = (s or "").strip().replace("Z", "+00:00")
    try:
        d = datetime.datetime.fromisoformat(s)
    except ValueError:
        return None, None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    d = d.astimezone(PRAGUE)
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M")


def nearest_card(a):
    """Vrátí nejbližšího předka, který obsahuje <time> (= karta jedné akce)."""
    card = a.parent
    for _ in range(4):
        if card is None:
            return None
        if card.find("time") is not None:
            return card
        card = card.parent
    return None


def fetch_detail(url):
    """Z detailu akce vytáhne cenu, lineup, popis a blurb. Best-effort; chyby ignoruje."""
    info = {"price": "", "lineup": [], "blurb": "", "desc": ""}
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
    except Exception:
        return info
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    # cena: za labelem "Vstupné"
    m = re.search(r"Vstupn[ée]\s+(?:od\s+)?(\d[\d\s]*\s*Kč|Zdarma|Vstup zdarma|Vyprodáno)", text)
    if m:
        info["price"] = re.sub(r"\s+", " ", m.group(1)).strip()
    elif "Vyprodáno" in text:
        info["price"] = "vyprodáno"
    # lineup: odkazy na umělce (ID začíná "p", např. /cs/metastavy/pzstnwf/)
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"^/cs/[^/]+/p[a-z0-9]+/?$")):
        nm = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
        k = nm.lower()
        if nm and k not in seen and 1 < len(nm) < 60:
            seen.add(k)
            info["lineup"].append(nm)
    info["lineup"] = info["lineup"][:6]
    # popis: nejdelší odstavec
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 60]
    if paras:
        info["desc"] = max(paras, key=len)[:240]
    # blurb: přednostně tučná úvodní věta (teaser), jinak první věta popisu
    lead = ""
    for tag in soup.find_all(["strong", "b"]):
        t = tag.get_text(" ", strip=True)
        if 20 <= len(t) <= 200:
            lead = t
            break
    if lead:
        info["blurb"] = lead[:120]
    elif info["desc"]:
        info["blurb"] = re.split(r"(?<=[.!?])\s", info["desc"])[0][:90]
    return info


def fetch_events(today):
    out, seen = [], set()
    horizon = today + datetime.timedelta(weeks=WEEKS_AHEAD)
    try:
        r = requests.get(GOOUT_BASE, headers=UA, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"[error] nešlo načíst GoOut: {e}", file=sys.stderr)
        return out
    soup = BeautifulSoup(r.text, "html.parser")

    # akce = <a class="title" title="..." href="/cs/<slug>/<id>/">
    for a in soup.find_all("a", attrs={"title": True, "href": re.compile(r"^/cs/")}):
        if "title" not in (a.get("class") or []):
            continue
        href = a.get("href", "")
        if "/listky/" in href:
            continue
        title = (a.get("title") or "").strip()
        if not title:
            continue
        card = nearest_card(a)
        if card is None:
            continue
        t = card.find("time")
        date, time = parse_iso(t.get("datetime")) if t else (None, None)
        if not date:
            continue
        if date < today.strftime("%Y-%m-%d") or date > horizon.strftime("%Y-%m-%d"):
            continue
        # kategorie = text před první čárkou v divu s časem
        cat_div = t.find_parent("div")
        category = cat_div.get_text(" ", strip=True).split(",")[0].strip() if cat_div else ""
        if category.lower() not in MUSIC_CATS:
            continue
        # místo = další /cs/ odkaz v kartě, jehož text sedí na VENUE_MAP
        venue_id = None
        for va in card.find_all("a", href=re.compile(r"^/cs/")):
            if va is a or "/listky/" in (va.get("href") or ""):
                continue
            vt = (va.get_text(" ", strip=True) or "").lower().strip()
            if vt in VENUE_MAP:
                venue_id = VENUE_MAP[vt]
                break
        if not venue_id:
            continue
        key = (title.lower(), date)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title, "date": date, "time": time, "venue": venue_id,
            "genres": genre_for(title, category),
            "ticket": "https://goout.net" + href, "category": category,
        })
    out.sort(key=lambda e: e["date"])
    out = out[:MAX_EVENTS]
    if out:
        print(f"[info] dotahuji detaily {len(out)} akcí (cena, lineup, popis)…", file=sys.stderr)
    for e in out:
        d = fetch_detail(e["ticket"])
        e["price"], e["lineup"], e["blurb"], e["desc"] = d["price"], d["lineup"], d["blurb"], d["desc"]
    return out


# ---------- práce s index.html ----------
def js_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


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


def build_item(idx, e):
    feat = "true" if idx <= 2 else "false"
    genres = ",".join(f'"{g}"' for g in e["genres"])
    lineup = ",".join('"%s"' % js_escape(x) for x in e.get("lineup", []))
    price = js_escape(e.get("price") or "vstupenky na GoOut")
    blurb = js_escape(e.get("blurb") or e["title"])[:90]
    desc = js_escape(e.get("desc") or "")
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
    existing_pairs = set()
    for it in kept:
        tt = re.search(r'title\s*:\s*"([^"]*)"', it)
        dd = re.search(r'date\s*:\s*"([^"]*)"', it)
        if tt and dd:
            existing_pairs.add((tt.group(1).lower(), dd.group(1)))
    fresh = [e for e in events if (e["title"].lower(), e["date"]) not in existing_pairs]
    new_items = [build_item(i + 1, e) for i, e in enumerate(fresh)]
    new_src = src[:start + 1] + "\n" + ",\n".join(kept + new_items) + "\n" + src[end:]
    if new_src.count("</html>") != 1:
        print("[error] po úpravě není právě jedno </html> — NEUKLÁDÁM", file=sys.stderr)
        return 1
    print(f"[info] ponecháno {len(kept)} ostatních, doplněno {len(new_items)} {MODE} "
          f"({len(events) - len(fresh)} přeskočeno jako duplikát)")
    if dry_run:
        print("[dry-run] nic se nezapsalo. Nové akce:")
        for e in fresh:
            lu = (" · " + ", ".join(e.get("lineup", []))) if e.get("lineup") else ""
            print(f"   {e['date']} {e['time']}  {e['venue']:12s} {'/'.join(e['genres']):12s} {(e.get('price') or ''):12s} {e['title']}{lu}")
        return 0
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(new_src)
    print(f"[ok] {INDEX_FILE} zapsán ({len(new_src)} znaků).")
    if fresh:
        with open("report.txt", "a", encoding="utf-8") as rf:
            rf.write(f"\n— {MODE.upper()} — doplněno {len(fresh)} akcí:\n")
            for e in fresh:
                lu = (" — " + ", ".join(e.get("lineup", []))) if e.get("lineup") else ""
                rf.write(f"  • {e['date']} {e['time']}  {e['venue']}  [{'/'.join(e['genres'])}]  "
                         f"{e.get('price') or ''}  {e['title']}{lu}\n")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="jen vypsat, nic nezapisovat")
    args = ap.parse_args()
    today = datetime.date.today()
    print(f"[info] {today} — stahuji GoOut Brno…")
    events = fetch_events(today)
    print(f"[info] nalezeno {len(events)} hudebních akcí v našich podnicích.")
    if not events:
        print("[warn] 0 akcí — GoOut možná změnil strukturu; pošli výstup debug_goout.py.")
        return 0
    return update_index(events, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
