#!/usr/bin/env python3
"""Diagnostika GoOutu — zjistí, jak parsovat. Spusť: python debug_goout.py
Výstup je krátký, zkopíruj ho celý zpátky do chatu."""
import re, json, requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
URL = "https://goout.net/cs/brno/akce/lezjyvlkk/"
h = requests.get(URL, headers=UA, timeout=30).text

print("LEN:", len(h))
print("has __NEXT_DATA__:", "__NEXT_DATA__" in h)
print("has ld+json   :", "application/ld+json" in h)
print("has 'Fléda':", "Fléda" in h, "| 'Kabinet':", "Kabinet" in h,
      "| 'Koncerty':", "Koncerty" in h, "| 'Metastavy':", "Metastavy" in h)

# JSON-LD?
ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)
print("\n# LD+JSON bloků:", len(ld))
if ld:
    try:
        d = json.loads(ld[0])
        print("LD[0] typ:", type(d).__name__,
              "keys:", list(d.keys())[:10] if isinstance(d, dict) else "(list)")
        print(json.dumps(d, ensure_ascii=False)[:700])
    except Exception as e:
        print("LD parse error:", e)

# __NEXT_DATA__?
m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
if m:
    print("\n# __NEXT_DATA__ len:", len(m.group(1)))
    print(m.group(1)[:300])

# vzorek odkazů na akce/místa
print("\n# vzorek /cs/ odkazů:")
for a in re.findall(r'href="((?:/cs/|https://goout\.net/cs/)[^"]+)"', h)[:14]:
    print(" ", a)

# okolí prvního výskytu 'Koncerty' (struktura karty)
i = h.find("Koncerty")
if i > 0:
    print("\n# HTML okolo 'Koncerty' (400 znaků):")
    print(h[i-200:i+200])
