#!/usr/bin/env python3
"""IG diagnostika (READ-ONLY): ukáže, co grabber z každého účtu VEZME a co ZAHODÍ a proč.
Nástroj na ladění quality filtru — NEpíše cache, NEcommituje. Vidíš reálné popisky + důvod.

    python ig_debug.py <ig_username>                 # projede všechny účty z IG_ACCOUNTS
    python ig_debug.py <ig_username> vibeclubbrno bassproof   # jen vybrané účty

Vyžaduje přihlášenou instaloader session (stejnou jako ig_local.py, default: ig.grabber).
Důvody zamítnutí (viz _parse_ig_caption): no-date, bad-date, out-of-range,
logistics, no-signal, no-venue, no-title. 'ok' = akce prošla.
"""
import datetime
import sys
import time

import grab_underground as gu


def main():
    if len(sys.argv) < 2:
        print("Použití: python ig_debug.py <ig_username> [ucet ...]", file=sys.stderr)
        return 1
    user = sys.argv[1]
    only = set(sys.argv[2:])
    today = datetime.date.today()
    horizon = today + datetime.timedelta(weeks=gu.g.WEEKS_AHEAD)
    cutoff = time.time() - gu.IG_LOOKBACK_DAYS * 86400

    import instaloader
    L = instaloader.Instaloader(quiet=True, max_connection_attempts=1, request_timeout=20.0)
    try:
        L.load_session_from_file(user)
    except Exception as e:
        print(f"[chyba] session '{user}' nenačtena: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    s = L.context._session
    s.headers.update(gu.IG_HEADERS)

    tally, total_posts = {}, 0
    for handle, venue in gu.IG_ACCOUNTS.items():
        if only and handle not in only:
            continue
        print(f"\n=== @{handle}   (default venue: {venue}) ===")
        try:
            info = s.get(f"https://i.instagram.com/api/v1/users/{handle}/usernameinfo/", timeout=20)
            info.raise_for_status()
            pk = info.json()["user"]["pk"]
            feed = s.get(f"https://i.instagram.com/api/v1/feed/user/{pk}/?count={gu.IG_MAX_POSTS}", timeout=20)
            feed.raise_for_status()
        except Exception as e:
            print(f"  [CHYBA API] {type(e).__name__}: {str(e)[:90]}")
            continue
        for it in feed.json().get("items", []):
            ts = it.get("taken_at") or 0
            if ts and ts < cutoff:
                break
            total_posts += 1
            cap = (it.get("caption") or {}).get("text") or ""
            post_date = datetime.date.fromtimestamp(ts) if ts else today
            ev, reason = gu._parse_ig_caption(cap, venue, today, horizon, post_date)
            tally[reason] = tally.get(reason, 0) + 1
            first = " ".join(cap.strip().split())[:75]     # 1. řádek zploštěný
            if ev:
                print(f"  [OK]  {ev['date']} {ev['time']} {ev['venue']:11s} {'/'.join(ev['genres'])[:10]:10s} -> {ev['title'][:42]}")
            else:
                print(f"  [--]  {reason:12s} | {first}")
        time.sleep(2)   # buď hodný na rate-limit (stejně jako grabber)

    print(f"\n=== SOUHRN ({total_posts} postů) ===")
    for r, n in sorted(tally.items(), key=lambda x: -x[1]):
        mark = "OK " if r == "ok" else "   "
        print(f"  {mark}{n:3d}  {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
