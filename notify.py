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


def _lineup(item):
    m = re.search(r"lineup\s*:\s*\[([^\]]*)\]", item)
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
            "title": _field(it, "title"), "lineup": _lineup(it), "ticket": _field(it, "ticket"),
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


def send_mail(to, token, evs):
    user, pw = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    rows = ""
    for e in evs[:MAX_PER_MAIL]:
        tick = (f' · <a href="{html.escape(e["ticket"])}">vstupenky</a>'
                if e["ticket"] and e["ticket"] != "#" else "")
        rows += (f'<li style="margin:9px 0"><b>{html.escape(e["title"])}</b><br>'
                 f'<span style="color:#777">{e["date"]} · {html.escape(e["venue"])}</span>{tick}</li>')
    unsub = f'{SITE}/unsubscribe?e={html.escape(to)}&t={html.escape(token)}'
    body = (
        '<div style="font-family:system-ui,-apple-system,sans-serif;max-width:560px;color:#161208">'
        '<h2>BRNO SCÉNA — nové akce u tvých oblíbených</h2>'
        f'<ul style="padding-left:18px">{rows}</ul>'
        f'<p><a href="{SITE}/#/sleduju">Otevřít na webu →</a></p>'
        '<hr style="border:none;border-top:1px solid #ddd;margin:20px 0">'
        '<p style="font-size:12px;color:#999">Dostáváš to, protože sleduješ kluby/umělce na BRNO SCÉNA. '
        f'<a href="{unsub}">Odhlásit se</a>.</p></div>'
    )
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = f"BRNO SCÉNA — {len(evs)} {'nová akce' if len(evs) == 1 else 'nových akcí'} pro tebe"
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
