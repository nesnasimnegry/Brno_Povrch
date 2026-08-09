#!/usr/bin/env python3
"""Lokální IG scrape z DOMÁCÍ (rezidenční) IP — tam, kde IG neblokuje jako v cloudu.

IG z GitHub Actions (datacenter IP) = checkpoint + 429. Řešení: scrapovat z tvého PC.
Tenhle skript naplní data/ig_events.json (sticky cache) a pushne ho; denní cloud grab
ho pak sám roznese na web (fetch_instagram čte tu cache i když je IG jinak blokované).

JEDNORÁZOVÉ NASTAVENÍ (v tomhle adresáři):
    pip install instaloader
    instaloader --login=<TVUJ_ODPADNI_IG_UCET>     # zeptá se na heslo; checkpoint potvrď v IG appce/e-mailu
    # (session se uloží; heslo se nikam nezapisuje)

SPUŠTĚNÍ (klidně přes Windows Plánovač úloh 1× denně):
    python ig_local.py <TVUJ_ODPADNI_IG_UCET>
"""
import datetime
import os
import subprocess
import sys


def run(*args):
    print("$", " ".join(args))
    return subprocess.run(args).returncode


def main():
    if len(sys.argv) < 2:
        print("Použití: python ig_local.py <ig_username>", file=sys.stderr)
        return 1
    os.environ["IG_USER"] = sys.argv[1]        # fetch_instagram podle toho načte session

    import grab_underground as gu
    today = datetime.date.today()
    evs = gu.fetch_instagram(today, dry_run=False)   # zapíše data/ig_events.json
    print(f"\n=== IG: {len(evs)} akcí v cache ===")
    for e in sorted(evs, key=lambda x: x["date"])[:40]:
        print(f"  {e['date']} {e['time']}  {e['venue']:12s} {'/'.join(e['genres']):12s} {e['title'][:50]}")

    run("git", "add", "data/ig_events.json")
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        run("git", "commit", "-m", "auto(ig): lokalni scrape IG -> cache")
        run("git", "pull", "--rebase", "origin", "main")
        run("git", "push")
        print("Pushnuto — denní cloud grab akce roznese na web.")
    else:
        print("Cache beze změny — necommituji.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
