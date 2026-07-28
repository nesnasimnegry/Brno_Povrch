#!/usr/bin/env python3
"""notify.py — e-mail odběratelům o NOVÝCH akcích jejich sledovaných klubů/DJ.

Běží ve workflow PO obou grabberech. Čte akce z public/index.html, odběratele
z chráněného /subscribers endpointu a seznam už-oznámených z data/announced.json.
Posílá personalizovaný HTML mail přes Gmail SMTP (s odhlašovacím odkazem).

Stabilní identita akce = "datum|venue|title" (auto-ID a1/u1 se přečíslují každý běh).

Použití:
    python notify.py --dry-run   # nic neodešle, jen vypíše, co by udělal
    python notify.py             # odešle maily + přepíše announced.json

Env (ve workflow ze secrets): SUBS_SECRET, GMAIL_USER, GMAIL_APP_PASSWORD.
"""
import argparse
import datetime
import html
import json
import os
import re
import smtplib
import ssl
import sys
from email.mime.text import MIMEText
from email.utils import formataddr

import requests
import grab_povrch as g

SITE = "https://snabba.pages.dev"
SUBSCRIBERS_URL = SITE + "/subscribers"
ANNOUNCED_FILE = "data/announced.json"
MAX_PER_MAIL = 15


def _field(item, name):
    m = re.search(name + r'\s*:\s*"((?:[^"\\]|\\.)*)"', item)
    return m.group(1).replace('\\"', '"').replace("\\\\", "\\") if m else ""


def _arr(item, name):
    m = re.search(name + r"\s*:\s*\[([^\]]*)\]", item)
    if not m:
        return []
    return [x.replace('\\"', '"') for x in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))]


def parse_events():
    """Vytáhne akce z index.html: id, date, venue, title, lineup, ticket, key."""
    src = open(g.INDEX_FILE, encoding="utf-8").read()
    m = re.search(r"const EVENTS=\[", src)
    if not m:
        return []
    start = m.end() - 1
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
        if ch in "\"'":
            in_str, q = True, ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return []
    out = []
    for it in g.split_items(src[start + 1:end]):
        e = {
            "id": g.item_id(it), "date": g.item_date(it), "venue": _field(it, "venue"),
            "title": _field(it, "title"), "lineup": _arr(it, "lineup"), "ticket": _field(it, "ticket"),
            "time": _field(it, "time"), "price": _field(it, "price"),
            "genres": _arr(it, "genres"), "venueName": _field(it, "venueName"),
        }
        if e["date"] and e["title"]:
            e["key"] = f'{e["date"]}|{e["venue"]}|{e["title"].lower().strip()[:60]}'
            out.append(e)
    return out


def matches(sub, e):
    """Sleduje odběratel daný klub nebo někoho z lineupu? (case-insensitive)"""
    if e["venue"].lower() in [v.lower() for v in sub.get("venues", [])]:
        return True
    low = [l.lower() for l in e["lineup"]]
    return any(a.lower() in low for a in sub.get("artists", []))


def fetch_subscribers():
    secret = os.environ.get("SUBS_SECRET", "")
    if not secret:
        print("[warn] SUBS_SECRET není nastaven — přeskakuji notifikace.", file=sys.stderr)
        return None
    try:
        r = requests.get(SUBSCRIBERS_URL, params={"secret": secret}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as ex:
        print(f"[warn] nešlo načíst odběratele: {ex}", file=sys.stderr)
        return None


_MONTHS_CS = ["LED", "ÚNO", "BŘE", "DUB", "KVĚ", "ČVN", "ČVC", "SRP", "ZÁŘ", "ŘÍJ", "LIS", "PRO"]
_VNAMES = None


def venue_names():
    """{id venue: název} z pole VENUES v index.html — ať mail píše 'Kabinet múz', ne 'kabinet'."""
    global _VNAMES
    if _VNAMES is None:
        _VNAMES = {}
        src = open(g.INDEX_FILE, encoding="utf-8").read()
        m = re.search(r"const VENUES=\[", src)
        if m:
            start = m.end() - 1
            depth, in_str, q, esc, end = 0, False, "", False, None
            for i in range(start, len(src)):
                ch = src[i]
                if in_str:
                    if esc: esc = False
                    elif ch == "\\": esc = True
                    elif ch == q: in_str = False
                    continue
                if ch in "\"'": in_str, q = True, ch
                elif ch == "[": depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0: end = i; break
            block = src[start:end] if end else ""
            _VNAMES = {vid: nm.replace('\\"', '"') for vid, nm in
                       re.findall(r'id:"([a-z0-9]+)"[^}]*?name:"((?:[^"\\]|\\.)*)"', block)}
    return _VNAMES


def _plural(n, one, few, many):
    return one if n == 1 else (few if 2 <= n <= 4 else many)


def _event_card(e):
    esc = html.escape
    d = e["date"]
    day, mon = str(int(d[8:10])), _MONTHS_CS[int(d[5:7]) - 1]
    vname = venue_names().get(e["venue"]) or e.get("venueName") or e["venue"]
    time = f' · {esc(e["time"])}' if e.get("time") else ""
    meta = " · ".join([x for x in e.get("genres", [])][:3])
    price = e.get("price", "")
    if price and (any(c.isdigit() for c in price) or "zdarma" in price.lower()):
        meta = (meta + "  ·  " if meta else "") + esc(price)
    tick = ""
    if e["ticket"] and e["ticket"] != "#":
        tick = (f'<a href="{esc(e["ticket"])}" style="display:inline-block;margin-top:11px;'
                f'font-family:\'Courier New\',monospace;font-size:12px;letter-spacing:.08em;'
                f'color:#ecc400;text-decoration:none;border-bottom:1px solid #7a5f00;'
                f'padding-bottom:2px;">VSTUPENKY →</a>')
    return (
        '<tr><td style="padding:0 0 12px;"><table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
        'style="background:#141210;border:1px solid #26231f;border-radius:12px;"><tr>'
        '<td width="72" valign="top" style="padding:18px 4px 18px 14px;text-align:center;">'
        f'<div style="font-family:\'Courier New\',monospace;color:#ecc400;font-size:26px;font-weight:700;line-height:1;">{day}</div>'
        f'<div style="font-family:\'Courier New\',monospace;color:#8a857b;font-size:11px;letter-spacing:.18em;margin-top:4px;">{mon}</div>'
        '</td>'
        '<td valign="top" style="padding:17px 16px 17px 8px;font-family:Arial,Helvetica,sans-serif;">'
        f'<div style="font-size:17px;font-weight:700;color:#efeae0;line-height:1.28;">{esc(e["title"])}</div>'
        f'<div style="font-size:13px;color:#b7b1a6;margin-top:6px;">▲ {esc(vname)}{time}</div>'
        + (f'<div style="font-family:\'Courier New\',monospace;font-size:11px;color:#8a857b;letter-spacing:.06em;margin-top:9px;">{meta}</div>' if meta else "")
        + tick +
        '</td></tr></table></td></tr>'
    )


def build_email(to, token, evs):
    """Vrátí (předmět, HTML tělo) notifikačního mailu — oddělené od odesílání kvůli náhledu."""
    n = len(evs)
    cards = "".join(_event_card(e) for e in evs[:MAX_PER_MAIL])
    unsub = f'{SITE}/unsubscribe?e={html.escape(to)}&t={html.escape(token)}'
    intro = ("U klubu nebo DJ-e, co sleduješ, přibyla akce. Ať ti neuteče:"
             if n == 1 else "U toho, co sleduješ, přibylo pár akcí. Ať ti žádná neuteče:")
    body = (
        '<!doctype html><html><body style="margin:0;padding:0;background:#0c0b0a;">'
        '<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#0c0b0a;">'
        '<tr><td align="center" style="padding:30px 14px;">'
        '<table width="600" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;max-width:600px;">'
        # header
        '<tr><td style="padding:2px 6px 24px;">'
        '<div style="font-family:\'Courier New\',monospace;font-size:12px;letter-spacing:.24em;color:#ecc400;">◤ TVÁ SCÉNA V BRNĚ</div>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:32px;font-weight:800;letter-spacing:-.5px;color:#efeae0;margin-top:9px;">BRNO SCÉNA</div>'
        '</td></tr>'
        # intro
        f'<tr><td style="padding:0 6px 22px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#c9c3b8;line-height:1.55;">{intro}</td></tr>'
        # cards
        + cards +
        # CTA
        '<tr><td style="padding:10px 6px 30px;">'
        f'<a href="{SITE}/#/sleduju" style="display:inline-block;background:#ecc400;color:#161208;'
        'font-family:\'Courier New\',monospace;font-weight:700;font-size:13px;letter-spacing:.12em;'
        'text-decoration:none;padding:15px 26px;border-radius:2px;">CELÝ PROGRAM →</a></td></tr>'
        # footer
        '<tr><td style="border-top:1px solid #26231f;padding:20px 6px 4px;font-family:\'Courier New\',monospace;'
        'font-size:11px;color:#7a756b;line-height:1.8;">'
        'Chodí ti to, protože na BRNO SCÉNA sleduješ kluby a DJ-e.<br>'
        f'Nechceš už? <a href="{unsub}" style="color:#ecc400;text-decoration:none;">Odhlásit jedním klikem</a>.'
        '</td></tr></table></td></tr></table></body></html>'
    )
    subj = ("Přibyla nová akce u tvých oblíbených" if n == 1
            else f"Přibyly {n} " + _plural(n, "", "nové akce", "nových akcí").strip() + " u tvých oblíbených")
    return subj, body


def send_mail(to, token, evs):
    user, pw = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    subj, body = build_email(to, token, evs)
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = subj
    msg["From"] = formataddr(("BRNO SCÉNA", user))
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="nic neodešle, jen vypíše")
    args = ap.parse_args()

    today = datetime.date.today().strftime("%Y-%m-%d")
    events = [e for e in parse_events() if e["date"] >= today]
    try:
        announced = set(json.load(open(ANNOUNCED_FILE, encoding="utf-8")))
    except Exception:
        announced = set()
    new = [e for e in events if e["key"] not in announced]
    print(f"[info] {len(events)} nadcházejících akcí, {len(new)} nových (neoznámených).")

    subs = fetch_subscribers()
    if subs is None:
        print("[info] bez odběratelů/secretu — announced.json neměním.")
        return 0
    print(f"[info] {len(subs)} odběratelů.")

    sent = 0
    for sub in subs:
        matched = [e for e in new if matches(sub, e)]
        if not matched:
            continue
        if args.dry_run:
            print(f"[dry-run] → {sub.get('email')}: {len(matched)} akcí "
                  f"({', '.join(e['title'][:28] for e in matched[:3])}…)")
        else:
            try:
                send_mail(sub["email"], sub.get("token", ""), matched)
                sent += 1
                print(f"[ok] mail → {sub['email']} ({len(matched)} akcí)")
            except Exception as ex:
                print(f"[error] mail {sub.get('email')} selhal: {ex}", file=sys.stderr)

    if not args.dry_run:
        os.makedirs("data", exist_ok=True)
        json.dump(sorted(e["key"] for e in events),
                  open(ANNOUNCED_FILE, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[ok] odesláno {sent} mailů; announced.json přepsán ({len(events)} klíčů).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
