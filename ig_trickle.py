#!/usr/bin/env python3
"""Trickle IG scrape pro always-on krabičku (Raspberry Pi / starý mobil / PC nechané zapnuté).

Místo jedné denní dávky (ig_local.py) scrapne jen K účtů za běh z náhodně zamíchané fronty;
až se fronta vyprázdní (kolo hotové), pushne cache. Cron pouštěj cca každých 30-45 min (+jitter).
Rozprostřením přes den mizí BURST — hlavní spouštěč IG bloku 'feedback_required / Try Again Later'.

Session i chování je stejné jako u ig_local.py (přihlášená session, feed+reels+stories+vize),
jen se to dělá po kouskách. Vyžaduje přihlášenou instaloader session (viz ig_session.py).

Použití:  python ig_trickle.py <ig_username> [K]      # K = kolik účtů za běh (default 1)
"""
import datetime
import json
import os
import random
import subprocess
import sys

QUEUE_FILE = "data/ig_queue.json"     # zbývající účty aktuálního kola (lokální stav, v .gitignore)


def run(*args):
    print("$", " ".join(args))
    return subprocess.run(args).returncode


def main():
    if len(sys.argv) < 2:
        print("Použití: python ig_trickle.py <ig_username> [K]", file=sys.stderr)
        return 1
    os.environ["IG_USER"] = sys.argv[1]        # fetch_instagram podle toho načte session
    k = max(1, int(sys.argv[2])) if len(sys.argv) > 2 else 1

    import grab_underground as gu
    try:
        queue = json.load(open(QUEUE_FILE, encoding="utf-8"))
        if not isinstance(queue, list):
            queue = []
    except Exception:
        queue = []
    if not queue:                              # prázdná fronta → nové kolo (zamíchané pořadí)
        queue = list(gu.IG_ACCOUNTS.keys())
        random.shuffle(queue)
        print(f"[info] nové kolo: {len(queue)} účtů zamícháno", file=sys.stderr)

    picked, rest = queue[:k], queue[k:]
    print(f"[info] trickle: scrapuju {picked} (po tomto zbývá {len(rest)})", file=sys.stderr)
    gu.fetch_instagram(datetime.date.today(), dry_run=False, only=picked)   # updatne cache o vybrané

    os.makedirs("data", exist_ok=True)
    json.dump(rest, open(QUEUE_FILE, "w", encoding="utf-8"))

    if not rest:                               # kolo hotové → pushni cache (jednou za kolo, ne po účtu)
        run("git", "add", "data/ig_events.json")
        if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
            run("git", "commit", "-m", "auto(ig): trickle kolo -> cache")
            run("git", "pull", "--rebase", "origin", "main")
            run("git", "push", "origin", "main")
            print("Kolo hotové — pushnuto, cloud grab akce roznese na web.", file=sys.stderr)
        else:
            print("Kolo hotové — cache beze změny, necommituji.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
