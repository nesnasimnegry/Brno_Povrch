#!/usr/bin/env python3
"""Import IG session z prohlížeče (kde jsi přihlášený) -> instaloader session.

Obchází programové přihlašování, které IG blokuje checkpointem. Přihlas se na
instagram.com (účet ig.grabber) ve Firefoxu / Chrome a spusť tenhle skript —
"půjčí si" cookies, ověří kdo je přihlášený a uloží session pro grabber.

Použití:  python ig_session.py
"""
import sys

try:
    import browser_cookie3
except ImportError:
    print("Chybí browser_cookie3 — nainstaluj:  pip install browser_cookie3", file=sys.stderr)
    sys.exit(2)
import instaloader


def main():
    for name in ("firefox", "chrome", "edge", "brave", "chromium", "opera", "librewolf", "vivaldi"):
        loader = getattr(browser_cookie3, name, None)
        if loader is None:
            continue
        try:
            cj = loader(domain_name="instagram.com")
        except Exception as e:
            print(f"  {name}: nešlo přečíst cookies ({type(e).__name__})")
            continue
        if not len(cj):
            continue
        L = instaloader.Instaloader(quiet=True, max_connection_attempts=1, request_timeout=20.0)
        L.context._session.cookies.update(cj)
        try:
            who = L.test_login()
        except Exception as e:
            print(f"  {name}: cookies jsou, ale ověření selhalo ({type(e).__name__})")
            who = None
        if who:
            L.context.username = who
            L.save_session_to_file()
            with open("ig_user.txt", "w", encoding="utf-8") as f:
                f.write(who)
            print(f"\nOK — session z prohlížeče '{name}' uložena pro účet '{who}'.")
            print("Teď už scrape poběží přihlášeně. Spusť BRNO-IG.bat / ig_local.py.")
            return 0
    print("\nNenašel jsem přihlášení na Instagram v žádném prohlížeči.")
    print("Přihlas se na https://instagram.com (účet ig.grabber) v Chrome nebo Firefoxu")
    print("(Firefox bývá nejspolehlivější) a spusť to znovu.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
